import type { ScriptDocumentV2, RowGapV2, SupportingItemV2, StashOutlineEntryV2, StashOriginV2, StashRowGroupV2, NarrationBlockV2, NarratedVisualPayloadV2, VisualOnlyBlockV2 } from "./generated/contracts-v2.js";
import type { AuthoringDiagnosticV2, VisualSequenceEditCommandV2, VisualSequenceEditResultV2 } from "./authoring-v2.js";
import { applyVisualSequenceEditV2 } from "./authoring-v2-edits.js";
import { validateScriptDocumentV2 } from "./authoring-v2-validation.js";
import { applyStageDirectionEditV2, defaultDirectionNarrationRowV2, type StageDirectionEditCommandV2 } from "./authoring-v2-stage-direction-edits.js";
import { applyStashRowEditV2 } from "./authoring-v2-stash.js";
import { markStashOriginEditedV2, preserveStashOriginAfterEditV2 } from "./authoring-v2-stash-origin.js";
import { copyStashNoteAsSpokenV2, invalidateChangedStashSourceLinksV2, stashChecklistV2, stashNoteContentStampV2 } from "./authoring-v2-stash-checklist.js";
import { trimResearchClipOccurrenceV2 } from "./authoring-v2-research-snapshot.js";
import { sameAuthoringJsonV2 } from "./authoring-v2-json.js";
import { chooseReturnSlotV2, freezeOriginalParentContextV2, freezeOriginalSiblingCandidatesV2 } from "./authoring-v2-stash-return-location.js";
import type { SaveStashGroupCommandV2 } from "./authoring-v2-stash-groups.js";
import { liftVisualV2 } from "./authoring-v2-visual-lifecycle.js";
import {
  appendWordlessV2, defaultWordlessHoldV2, liftWordlessV2, newWordlessPlaceholderV2,
  LEGACY_VISUAL_HOLD_MS, NEW_VISUAL_HOLD_MS, preserveWordlessHoldV2,
  promoteWordlessNarrationV2, toNarratedPlacementV2, wordlessPlacementsV2,
} from "./authoring-v2-wordless.js";
import { spliceNarrationTextV2 } from "./authoring-v2-narration-text.js";
import { spokenTokensV2 } from "./authoring-v2-stage-directions.js";
import { attachVisualV2, emptyRowCoverageV2, isCoverageRefusalV2, reconcileNarrationTextCoverageV2 } from "./authoring-v2-coverage.js";
import {
  applySplitOrJoinV2,
  isSplitOrJoinCommandV2,
  joinReversesSplitV2,
  type JoinRowsCommandV2,
  type SplitRowCommandV2,
} from "./authoring-v2-row-split-join.js";
import {
  isInsertStashNoteWordsCommandV2,
  isStashSelectedWordsCommandV2,
  prepareStashWordCutV2,
  spliceSpokenStashNoteV2,
  type InsertStashNoteWordsCommandV2,
  type StashSelectedWordsCommandV2,
} from "./authoring-v2-stash-words.js";

type Block = ScriptDocumentV2["activeDraft"]["blocks"][number];
type Row = Exclude<Block, { type: "section" }>;
export type { RowGapV2 } from "./generated/contracts-v2.js";

/** D135/D146: use the existing ordered visuals-only row when clearing several pictures. */
function clearToVisualOnlyRow(row: NarrationBlockV2): VisualOnlyBlockV2 | AuthoringDiagnosticV2 | null {
  const sequence = row.primaryVisualSequence;
  if (!sequence) return null;
  const slots = sequence.slots;
  const visuals = [
    ...slots.flatMap((slot) => slot.kind === "content" && slot.payload.kind === "visual"
      ? [{ id: slot.id, version: slot.version, payload: slot.payload }] : []),
    ...(row.unattachedVisuals ?? []).map((item) => ({ id: item.slotId, version: item.version, payload: item.payload })),
  ];
  if (visuals.length < 2) return null;
  if (slots.some((slot) => slot.kind === "content" && slot.playoutPolicy !== "match_structural_interval")) {
    return diagnostic("RANGE_SEQUENCE_UNRESOLVED", "A clip that plays to its own end cannot be moved to wordless playout without losing its timing.");
  }
  if (row.attachedFootage || row.notes.length || row.overlayEvents.length ||
      row.annotations?.length || row.performanceBeats?.length ||
      slots.some((slot) => slot.kind === "content" &&
        (slot.payload.kind === "undefined" || slot.payload.kind === "on_camera" && slot.payload.presenterChoiceId !== null))) {
    return diagnostic("RANGE_SEQUENCE_UNRESOLVED", "Review the row's additional picture or narration settings before clearing all its words.");
  }
  const placements = [];
  for (const { payload: visual } of visuals) {
    const { selectedSourceRange, sourceUsage, researchClip, frameBinding, ...payload } = visual;
    if (payload.pictureKind === "clip" && (!selectedSourceRange ||
        sourceUsage?.sourceInFrame !== selectedSourceRange.startFrame)) {
      return diagnostic("RANGE_SEQUENCE_UNRESOLVED", "Give each clip a selected source range before clearing its narration.");
    }
    placements.push({
      payload,
      visualOnlyTiming: { kind: "visual_only" as const, ...(selectedSourceRange
        ? { selectedSourceRange } : { durationOverrideMs: NEW_VISUAL_HOLD_MS }) },
      ...(researchClip ? { researchClip } : {}),
      ...(frameBinding ? { frameBinding } : {}),
    });
  }
  const [firstSlot, secondSlot, ...remainingSlots] = visuals.map(({ id, version, payload }) => ({
    id, version, visualId: payload.payloadId,
  }));
  return {
    type: "visual_only", id: row.id, orderKey: row.orderKey, version: row.version + 1,
    ...placements[0]!,
    additionalVisuals: [placements[1]!, ...placements.slice(2)],
    clearedNarration: {
      id: sequence.id, version: sequence.version,
      slots: [firstSlot!, secondSlot!, ...remainingSlots],
    },
    ...(row.stashOrigin ? { stashOrigin: row.stashOrigin } : {}),
    ...(row.stashChecklist ? { stashChecklist: row.stashChecklist } : {}),
  };
}

/**
 * Preserve every picture without assigning it a new cue. On Camera covers
 * the new narration until the writer attaches pictures to words.
 */
function restoreClearedNarration(
  row: VisualOnlyBlockV2,
  sequence: NonNullable<VisualOnlyBlockV2["clearedNarration"]>,
): NarrationBlockV2 | AuthoringDiagnosticV2 {
  const visuals = [row, ...(row.additionalVisuals ?? [])];
  const slots = new Map(sequence.slots.map((slot) => [slot.visualId, slot]));
  const restored = [];
  for (const visual of visuals) {
    const slot = slots.get(visual.payload.payloadId);
    const { audioPolicy } = visual.payload;
    const { selectedSourceRange, durationOverrideMs } = visual.visualOnlyTiming;
    // Four seconds is the new source-free default, not an authored nondefault
    // hold. It can be discarded when the restored visual waits for words.
    if (!slot || audioPolicy === "full" || durationOverrideMs !== undefined && durationOverrideMs !== NEW_VISUAL_HOLD_MS) {
      return diagnostic("RANGE_SEQUENCE_UNRESOLVED", "Review this row’s picture timing and audio before adding narration.");
    }
    const payload: NarratedVisualPayloadV2 = {
      ...visual.payload,
      audioPolicy,
      sourceUsage: selectedSourceRange ? { sourceInFrame: selectedSourceRange.startFrame } : null,
      ...(selectedSourceRange ? { selectedSourceRange } : {}),
      ...(visual.researchClip ? { researchClip: visual.researchClip } : {}),
      ...(visual.frameBinding ? { frameBinding: visual.frameBinding } : {}),
    };
    restored.push({ slotId: slot.id, version: slot.version + 1, payload });
  }
  return {
    type: "narration", id: row.id, orderKey: row.orderKey, version: row.version,
    state: "active", timingPolicy: "narration_spine",
    text: "", tokens: [], overlayEvents: [], notes: [],
    primaryVisualSequence: {
      id: sequence.id, version: sequence.version + 1,
      slots: emptyRowCoverageV2(sequence.id),
    },
    unattachedVisuals: restored,
    ...(row.stashOrigin ? { stashOrigin: row.stashOrigin } : {}),
    ...(row.stashChecklist ? { stashChecklist: row.stashChecklist } : {}),
  };
}

/** Exact outline gap for a deliberate Stash drop (not an active-Draft RowGap). */
export type StashReturnDestinationV2 = RowGapV2 & { parentRowId: string | null };

export type RowEditCommandV2 =
  | { kind: "move_rows"; rowIds: string[]; destination: RowGapV2 }
  | { kind: "move_section"; sectionId: string; destination: { afterSectionId: string | null; beforeSectionId: string | null } }
  | { kind: "create_section"; sectionId: string; title: string; destination: RowGapV2 }
  | { kind: "rename_section"; sectionId: string; title: string }
  | { kind: "delete_section_break"; sectionId: string }
  | { kind: "stash_rows"; rowIds: string[]; bundleId: string; destination?: StashReturnDestinationV2 }
  | StashSelectedWordsCommandV2
  | InsertStashNoteWordsCommandV2
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
  | { kind: "rename_stash_section"; sectionId: string; title: string }
  | { kind: "delete_stash_section"; sectionId: string }
  | { kind: "move_stash_rows"; rowIds: string[]; sectionId: string | null }
  | { kind: "create_stash_note"; bundleId: string; row: NarrationBlockV2; sectionId: string | null; parentRowId: string | null; afterRowId: string | null; mode?: "default_direction" | "authored" }
  | { kind: "create_stash_clip"; bundleId: string; row: VisualOnlyBlockV2; sectionId: string | null; parentRowId: string | null; afterRowId: string | null; atStart?: true }
  /** Stash one visual (D91): lift it out of its row into a new Stash item with its source and trim. Never On Camera. */
  | { kind: "stash_visual"; rowId: string; slotId: string; bundleId: string; stashRowId: string; sectionId: string | null; parentRowId: string | null; afterRowId: string | null }
  | { kind: "insert_stash_visual"; stashRowId: string; destinationRowId: string; destinationSlotId: string }
  | { kind: "attach_stash_footage"; noteRowId: string; clipRowId: string }
  | { kind: "replace_stash_footage"; noteRowId: string; clipRowId: string; releasedBundleId: string }
  | { kind: "detach_stash_footage"; noteRowId: string; bundleId: string; destination?: StashReturnDestinationV2 }
  | { kind: "cleanup_blank_stash_note"; noteRowId: string; clipBundleId: string; clearText?: true }
  | { kind: "trim_research_clip"; clipRowId: string; edge: "in" | "out"; frame: number }
  | { kind: "trim_research_clip"; clipRowId: string; edge: "clear_out" }
  | { kind: "place_attached_footage"; noteRowId: string; destination: RowGapV2 }
  | { kind: "set_stash_outline"; entries: StashOutlineEntryV2[] }
  | { kind: "place_stash_rows"; rowIds: string[]; destination: RowGapV2; includeDescendants?: boolean }
  | { kind: "set_stash_completion"; rowId: string; completed: boolean }
  | { kind: "edit_row"; rowId: string; row: Row }
  | { kind: "edit_narration_text"; rowId: string; startOffset: number; endOffset: number; insertedText: string; editId: string }
  /** Rename this use of a clip/still, never its shared media source. Blank clears the alias. */
  | { kind: "rename_visual_placement"; rowId: string; payloadId: string; name: string }
  /** Reorder the first and additional visuals together without changing their metadata. */
  | { kind: "reorder_visual_only"; rowId: string; payloadIds: string[] }
  | { kind: "set_visual_only_hold"; rowId: string; payloadId: string; holdSeconds: number }
  /** Add a new source-free picture or promote an empty narration row, in one saved revision. */
  | { kind: "add_visual_to_wordless_row"; rowId: string; payloadId: string; slotId: string; visualType: "onscreen_placeholder" | "need_to_find" }
  /** Move one whole wordless placement. A narrated target receives it waiting for words. */
  | { kind: "move_wordless_visual"; sourceRowId: string; payloadId: string; destinationRowId: string;
      destinationSlotId?: string; replacementPayloadId?: string; expectedDestinationSequenceVersion?: number }
  /** Explicitly match or unmatch one untimed visual to one saved music cue. */
  | { kind: "set_visual_only_audio_match"; rowId: string; payloadId: string; cueId: string | null }
  /** Delete one saved music cue and restore fixed holds for visuals explicitly matched to it. */
  | { kind: "delete_row_audio_span"; cueId: string }
  | { kind: "create_row"; row: Row; destination: RowGapV2 }
  | { kind: "delete_rows"; rowIds: string[] }
  | SplitRowCommandV2
  | JoinRowsCommandV2
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
  placementCounts?: { copiedNotes: number; movedClips: number; movedSavedRows: number; skippedCompleted: number; attachedFootageCopies: number };
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
    if (value.kind === "edit_narration_text") {
      return isJsonValue(value) && exactKeys(value, ["kind", "rowId", "startOffset", "endOffset", "insertedText", "editId"]) &&
        typeof value.rowId === "string" && value.rowId.length > 0 &&
        typeof value.editId === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu.test(value.editId) &&
        Number.isSafeInteger(value.startOffset) && Number.isSafeInteger(value.endOffset) &&
        typeof value.insertedText === "string";
    }
    if (value.kind === "edit_row") {
      return exactKeys(value, ["kind", "rowId", "row"]) && typeof value.rowId === "string" && value.rowId.length > 0 &&
        rowPayload(value.row) && value.row.id === value.rowId;
    }
    if (value.kind === "create_row") {
      return exactKeys(value, ["kind", "row", "destination"]) && rowPayload(value.row) &&
        !Object.hasOwn(value.row, "stashOrigin") && !Object.hasOwn(value.row, "stashChecklist") &&
        !Object.hasOwn(value.row, "clearedNarration") && rowGapPayload(value.destination);
    }
    if (value.kind === "delete_rows") {
      return exactKeys(value, ["kind", "rowIds"]) && rowIdsPayload(value.rowIds) && value.rowIds.length > 0 && new Set(value.rowIds).size === value.rowIds.length;
    }
    return false;
  } catch {
    return false;
  }
}

const uuid = (item: unknown): item is string => typeof item === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu.test(item);

/** Reserve all document UUID values, including IDs in media, Stash and extras. */
function documentUuids(value: unknown, result = new Set<string>()): Set<string> {
  if (typeof value === "string") {
    if (uuid(value)) result.add(value.toLowerCase());
  } else if (value && typeof value === "object") {
    for (const child of Object.values(value)) documentUuids(child, result);
  }
  return result;
}

function validVisualOnlyCommand(value: unknown): boolean {
  if (!plainObject(value) || !isJsonValue(value)) return false;
  if (value.kind === "delete_row_audio_span") {
    return exactKeys(value, ["kind", "cueId"]) && typeof value.cueId === "string" && value.cueId.length > 0;
  }
  if (value.kind === "move_wordless_visual") {
    const optional = ["destinationSlotId", "replacementPayloadId", "expectedDestinationSequenceVersion"]
      .filter((key) => Object.hasOwn(value, key));
    return exactKeys(value, ["kind", "sourceRowId", "payloadId", "destinationRowId", ...optional]) &&
      uuid(value.sourceRowId) && uuid(value.payloadId) && uuid(value.destinationRowId) &&
      (!Object.hasOwn(value, "destinationSlotId") || uuid(value.destinationSlotId)) &&
      (!Object.hasOwn(value, "replacementPayloadId") || uuid(value.replacementPayloadId)) &&
      (!Object.hasOwn(value, "expectedDestinationSequenceVersion") ||
        Number.isSafeInteger(value.expectedDestinationSequenceVersion) && (value.expectedDestinationSequenceVersion as number) >= 0);
  }
  if (value.kind === "add_visual_to_wordless_row") {
    return exactKeys(value, ["kind", "rowId", "payloadId", "slotId", "visualType"]) &&
      uuid(value.rowId) && uuid(value.payloadId) && uuid(value.slotId) &&
      (value.visualType === "onscreen_placeholder" || value.visualType === "need_to_find");
  }
  if (typeof value.rowId !== "string" || value.rowId.length === 0) return false;
  if (value.kind === "reorder_visual_only") {
    return exactKeys(value, ["kind", "rowId", "payloadIds"]) && rowIdsPayload(value.payloadIds) &&
      value.payloadIds.length > 1 && new Set(value.payloadIds).size === value.payloadIds.length;
  }
  if (value.kind === "set_visual_only_hold") {
    return exactKeys(value, ["kind", "rowId", "payloadId", "holdSeconds"]) &&
      typeof value.payloadId === "string" && value.payloadId.length > 0 && typeof value.holdSeconds === "number";
  }
  if (value.kind === "set_visual_only_audio_match") {
    return exactKeys(value, ["kind", "rowId", "payloadId", "cueId"]) &&
      typeof value.payloadId === "string" && value.payloadId.length > 0 &&
      (value.cueId === null || typeof value.cueId === "string" && value.cueId.length > 0);
  }
  return false;
}

function validRenameVisualPlacementCommand(value: unknown): boolean {
  return plainObject(value) && isJsonValue(value) &&
    exactKeys(value, ["kind", "rowId", "payloadId", "name"]) &&
    value.kind === "rename_visual_placement" &&
    typeof value.rowId === "string" && value.rowId.length > 0 &&
    typeof value.payloadId === "string" && value.payloadId.length > 0 &&
    typeof value.name === "string";
}

/** Locate one saved placement by payload identity, including waiting and wordless visuals. */
function rowVisualPlacements(row: NarrationBlockV2 | VisualOnlyBlockV2): Array<NarratedVisualPayloadV2 | VisualOnlyBlockV2["payload"]> {
  if (row.type === "visual_only") {
    return [row.payload, ...(row.additionalVisuals ?? []).map((visual) => visual.payload)];
  }
  return [
    ...(row.primaryVisualSequence?.slots ?? []).flatMap((slot) =>
      slot.kind === "content" && slot.payload.kind === "visual" ? [slot.payload] : []),
    ...(row.unattachedVisuals ?? []).map((visual) => visual.payload),
  ];
}

function draftSectionKind(kind: unknown): kind is "create_section" | "rename_section" | "delete_section_break" {
  return kind === "create_section" || kind === "rename_section" || kind === "delete_section_break";
}

/** Strict JSON command boundary; section IDs follow the document's UUID identity contract. */
function validDraftSectionCommand(value: unknown): boolean {
  if (!plainObject(value) || !isJsonValue(value) || typeof value.sectionId !== "string" ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.sectionId)) return false;
  if (value.kind === "delete_section_break") return exactKeys(value, ["kind", "sectionId"]);
  if (value.kind !== "create_section" && value.kind !== "rename_section") return false;
  if (typeof value.title !== "string" || value.title.trim().length === 0) return false;
  return value.kind === "create_section"
    ? exactKeys(value, ["kind", "sectionId", "title", "destination"]) && rowGapPayload(value.destination)
    : exactKeys(value, ["kind", "sectionId", "title"]);
}

/** Section organization commands must be exact plain JSON with a section UUID. */
function validStashSectionChangeCommand(value: unknown): boolean {
  if (!plainObject(value) || !isJsonValue(value) || typeof value.sectionId !== "string" ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.sectionId)) return false;
  if (value.kind === "delete_stash_section") return exactKeys(value, ["kind", "sectionId"]);
  return value.kind === "rename_stash_section" && exactKeys(value, ["kind", "sectionId", "title"]) &&
    typeof value.title === "string" && value.title.trim().length > 0;
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
      return exactKeys(value, ["kind", "noteRowId", "bundleId", ...(Object.hasOwn(value, "destination") ? ["destination"] : [])]) &&
        typeof value.bundleId === "string" && value.bundleId.length > 0 &&
        (!Object.hasOwn(value, "destination") || stashReturnDestinationPayload(value.destination));
    case "cleanup_blank_stash_note":
      return exactKeys(value, ["kind", "noteRowId", "clipBundleId", ...(Object.hasOwn(value, "clearText") ? ["clearText"] : [])]) &&
        (!Object.hasOwn(value, "clearText") || value.clearText === true) &&
        typeof value.clipBundleId === "string" && value.clipBundleId.length > 0;
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

function removeOrdinaryStashClip(document: ScriptDocumentV2, rowId: string, includeSavedVisuals = false): VisualOnlyBlockV2 | null {
  const entry = document.stashOutline?.find((candidate) => candidate.rowId === rowId);
  const bundle = document.stash?.find((candidate) => candidate.rows.some((row) => row.id === rowId));
  const row = bundle?.rows.find((candidate) => candidate.id === rowId);
  // Do not silently migrate supporting-item or origin references into an embedded owner.
  if (!entry || (entry.kind !== "clip" && !(includeSavedVisuals && entry.kind === "row")) ||
    !bundle || row?.type !== "visual_only" ||
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
    ...(clip.payload.framingPolicy !== undefined ? { framingPolicy: clip.payload.framingPolicy } : {}),
    ...(clip.payload.displayName !== undefined ? { displayName: clip.payload.displayName } : {}),
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
  asGroup = false,
): StashOutlineEntryV2[] | null {
  const result = structuredClone(entries);
  const selected = new Map(rows.map((row) => [row.id, row]));
  const returnedKinds = new Map(rows.map((row) => [row.id,
    row.stashOrigin?.returnEligible && row.stashOrigin.kind !== "row" ? row.stashOrigin.kind : "row"] as const));
  // An edited note cannot turn into an ordinary full row while carrying an
  // embedded clip owner. Never copy or silently detach that owned occurrence.
  // Group formation explicitly retains the full canonical note (and its owned
  // clip) as a member. Ordinary returns must never make that conversion.
  if (!asGroup && rows.some((row) => row.type === "narration" && row.attachedFootage &&
    returnedKinds.get(row.id) === "row" && !row.stashOrigin?.sourceNoteRowId)) return null;
  const sectionIds = new Set((document.stashSections ?? []).map((section) => section.id));
  const original = new Map(rows.map((row) => [row.id, row.stashOrigin] as const));
  const placed = new Set<string>();
  const cursors = new Map<string, string>();
  // #373: when several independent copies are saved together as full rows,
  // the run must keep its authored order. Their distinct source-note anchors
  // can otherwise insert the second copy *before* the first copy.
  const copiedBatchCursors = new Map<string, string>();

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
    if (!destination && rows.length > 1 && row.type === "narration" && row.stashOrigin?.sourceNoteRowId) {
      const key = `${parentRowId ?? "root"}:${sectionId ?? "unsectioned"}`;
      const predecessor = copiedBatchCursors.get(key);
      if (predecessor) insertAt = outlineSubtreeEnd(result, predecessor) + 1;
      copiedBatchCursors.set(key, row.id);
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
  const matchedRows = (document: ScriptDocumentV2, cueId: string): string[] => document.activeDraft.blocks.flatMap((block) => {
    if (block.type !== "visual_only") return [];
    const timings = [block.visualOnlyTiming, ...(block.additionalVisuals ?? []).map((visual) => visual.visualOnlyTiming)];
    return timings.some((timing) => timing.matchAudioDuration?.cueId === cueId) ? [block.id] : [];
  });
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
    const retainedRows = covered(nextLocations, span.startRowId, retainedEndRowId) ?? [];
    const stranded = matchedRows(before, span.id).filter((rowId) => oldRows.includes(rowId) && !retainedRows.includes(rowId));
    if (stranded.length > 0) {
      return {
        ...diagnostic("MUSIC_MATCH_STRANDED", "This move would shorten a music cue away from a matched still. Clear Match audio duration on the affected visual or keep it inside the cue, then try again."),
        blockId: stranded[0]!,
        entityId: span.id,
      };
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
export function applyRowEditV2(
  document: ScriptDocumentV2, expectedRevision: number, command: RowEditCommandV2,
  projectHoldMs = LEGACY_VISUAL_HOLD_MS,
): RowEditResultV2 {
  if (!plainObject(command)) return refused(document, "ROW_COMMAND_INVALID", "Provide a row edit command.");
  try {
    if (command.kind === "stash_rows" && (!isJsonValue(command) ||
      !exactKeys(command, Object.hasOwn(command, "destination") ? ["kind", "rowIds", "bundleId", "destination"] : ["kind", "rowIds", "bundleId"]) ||
      !rowIdsPayload(command.rowIds) || typeof command.bundleId !== "string" || command.bundleId.length === 0 ||
      Object.hasOwn(command, "destination") && !stashReturnDestinationPayload(command.destination))) {
      return refused(document, "ROW_COMMAND_INVALID", "Provide a valid Stash return and an exact optional outline drop destination.");
    }
    if (command.kind === "stash_selected_words" && (!isJsonValue(command) || !isStashSelectedWordsCommandV2(command))) {
      return refused(document, "ROW_COMMAND_INVALID", "Provide one exact word selection, source row and unused Stash IDs.");
    }
    if (command.kind === "insert_stash_note_words" && (!isJsonValue(command) || !isInsertStashNoteWordsCommandV2(command))) {
      return refused(document, "ROW_COMMAND_INVALID", "Provide one saved Stash note, receiving row and spoken-word gap.");
    }
    if (groupKind(command.kind) && !validGroupCommand(command)) return refused(document, "ROW_COMMAND_INVALID", "Provide an exact Stash group command with distinct row IDs and an unambiguous location.");
    if ((command.kind === "edit_row" || command.kind === "edit_narration_text" || command.kind === "create_row" || command.kind === "delete_rows") && !validAuthoredRowCommand(command)) return refused(document, "ROW_COMMAND_INVALID", "Provide a complete authored row edit command with exact row IDs and destinations.");
    if ((command.kind === "reorder_visual_only" || command.kind === "set_visual_only_hold" || command.kind === "set_visual_only_audio_match" || command.kind === "delete_row_audio_span" || command.kind === "add_visual_to_wordless_row" || command.kind === "move_wordless_visual") && !validVisualOnlyCommand(command)) return refused(document, "ROW_COMMAND_INVALID", "Provide an exact visual order, hold, audio-match, or wordless picture command.");
    if (command.kind === "rename_visual_placement" && !validRenameVisualPlacementCommand(command)) return refused(document, "ROW_COMMAND_INVALID", "Provide one visual placement and a text name, with no extra fields.");
    if (draftSectionKind(command.kind) && !validDraftSectionCommand(command)) return refused(document, "ROW_COMMAND_INVALID", "Provide an exact script section command with a valid ID, nonblank title, and current row gap.");
    if ((command.kind === "rename_stash_section" || command.kind === "delete_stash_section") && !validStashSectionChangeCommand(command)) {
      return refused(document, "ROW_COMMAND_INVALID", "Provide an exact Stash section command with a valid section ID and, for rename, a nonblank title.");
    }
    if (attachmentKind(command.kind) && (!isJsonValue(command) || !validAttachmentCommand(command))) return refused(document, "ROW_COMMAND_INVALID", "Provide an exact footage attachment command.");
    if (command.kind === "place_stash_rows" &&
      (!isJsonValue(command) ||
        !exactKeys(command, Object.hasOwn(command, "includeDescendants") ? ["kind", "rowIds", "destination", "includeDescendants"] : ["kind", "rowIds", "destination"]) ||
        !rowIdsPayload(command.rowIds) || !rowGapPayload(command.destination) ||
        Object.hasOwn(command, "includeDescendants") && typeof command.includeDescendants !== "boolean")) {
      return refused(document, "ROW_COMMAND_INVALID", "Provide a valid Stash placement with an optional boolean includeDescendants.");
    }
    if (command.kind === "set_stash_completion" &&
      (!isJsonValue(command) || !exactKeys(command, ["kind", "rowId", "completed"]) ||
      typeof command.rowId !== "string" || command.rowId.length === 0 || typeof command.completed !== "boolean")) {
      return refused(document, "ROW_COMMAND_INVALID", "Provide an exact Stash note or clip completion change.");
    }
    if (isStageDirectionKind(command.kind) && !validStageDirectionCommand(command)) return refused(document, "ROW_COMMAND_INVALID", "Provide a complete stage-direction edit command.");
    if ((command.kind === "split_row" || command.kind === "join_rows") && (!isJsonValue(command) || !isSplitOrJoinCommandV2(command))) {
      return refused(document, "ROW_COMMAND_INVALID", "Provide a complete split or join command: the row, the cursor or selected words, and for a split an unused new row ID.");
    }
  } catch {
    return refused(document, "ROW_COMMAND_INVALID", "Provide a complete row edit command with plain JSON values.");
  }
  const before = validateScriptDocumentV2(document);
  // A concurrently removed cue leaves an explicit stale match. Keep the
  // document editable so the author can clear it; the compiler remains
  // fail-closed while the link is present.
  if (before.diagnostics.some((item) => ["SCHEMA_INVALID", "ENTITY_ID_DUPLICATE", "BLOCK_ID_DUPLICATE", "ROW_REFERENCE_INVALID", "PLAIN_DIRECTION_INTENT_INVALID", "FOOTAGE_OWNER_DUPLICATE", "RESEARCH_CLIP_INVALID", "STASH_GROUP_INVALID", "CLEARED_NARRATION_INVALID"].includes(item.code))) return { ok: false, document, diagnostics: before.diagnostics };
  if (!Number.isSafeInteger(expectedRevision) || expectedRevision !== (document.rowEditRevision ?? 0) || expectedRevision === Number.MAX_SAFE_INTEGER) return refused(document, "ROW_REVISION_STALE", "The row document changed before this edit, or its revision cannot advance.");
  if (command.kind === "save_stash_group" && command.expectedRevision !== expectedRevision) {
    return refused(document, "ROW_REVISION_STALE", "A staged group Save must use the exact revision at which its member editor opened.");
  }

  // Existing single-member edit routes cannot bypass the group's atomic Save boundary.
  const grouped = new Set((document.stashGroups ?? []).flatMap((group) => group.rowIds));
  if ((command.kind === "edit_row" || command.kind === "edit_narration_text" || command.kind === "rename_visual_placement" || command.kind === "reorder_visual_only" || command.kind === "set_visual_only_hold" || command.kind === "set_visual_only_audio_match" || command.kind === "add_visual_to_wordless_row") && grouped.has(command.rowId) ||
    command.kind === "move_wordless_visual" && (grouped.has(command.sourceRowId) || grouped.has(command.destinationRowId)) ||
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
    const stageResult = { ...edited.document, rowEditRevision: expectedRevision + 1 };
    invalidateChangedStashSourceLinksV2(document, stageResult);
    const serialized = serializedDocument(stageResult);
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
  let placementCounts: RowEditResultV2["placementCounts"];
  let operationDiagnostics: AuthoringDiagnosticV2[] = [];
  if (command.kind === "stash_selected_words") {
    // Construct both sides before writing: an unsafe selection never leaves
    // half a note in Stash or removes only part of the narration text.
    const cut = prepareStashWordCutV2(document, command, documentUuids(document));
    if ("code" in cut) return { ok: false, document, diagnostics: [cut] };
    const index = blocks.findIndex((block) => block.id === command.rowId);
    blocks.splice(index, 1, cut.updated);
    const outline = ensureStashOutline(working);
    // Always prepend to unsectioned Stash (not the old afterRowId:null append
    // behaviour), preserving all existing section roots and child preorders.
    outline.unshift({ rowId: cut.saved.id, kind: cut.kind, sectionId: null, parentRowId: null });
    (working.stash ??= []).push({ id: command.bundleId, rows: [cut.saved], supportingItems: [] });
  } else if (command.kind === "insert_stash_note_words") {
    const entry = working.stashOutline?.find((candidate) => candidate.rowId === command.noteRowId);
    const source = stashRowById(working, command.noteRowId);
    const index = blocks.findIndex((block) => block.id === command.rowId);
    const target = blocks[index];
    if (!entry || entry.kind !== "note" || grouped.has(command.noteRowId) || source?.type !== "narration" || source.plainDirection !== true ||
      !source.text.trim() || source.tokens.length === 0) {
      return refused(document, "STASH_NOTE_CONTENT_INVALID", "Choose a nonblank Stash note with literal words.");
    }
    if (source.overlayEvents.length || source.annotations?.length || source.performanceBeats?.length ||
      source.unattachedVisuals?.length) {
      return refused(document, "STASH_NOTE_CONTENT_INVALID", "A note with additional word-owned objects needs an explicit placement review.");
    }
    if (target?.type !== "narration" || target.state !== "active" || target.plainDirection === true ||
      target.attachedFootage || !target.primaryVisualSequence) {
      return refused(document, "NARRATION_TEXT_TARGET_INVALID", "Choose an active spoken row with a supported visual sequence.");
    }
    if (!Number.isSafeInteger(target.version) || target.version === Number.MAX_SAFE_INTEGER ||
      !Number.isSafeInteger(target.primaryVisualSequence.version) || target.primaryVisualSequence.version === Number.MAX_SAFE_INTEGER) {
      return refused(document, "ROW_CONTENT_INVALID", "The receiving row version cannot advance.");
    }
    // Every use of the source note is a fresh occurrence. No link back to the
    // source is created: later edits/deletions cannot undo its completion.
    // Sorting acceptance can rewind rowEditRevision relative to an in-trial
    // edit. Include the edited row version and exact gap so a subsequent
    // insertion cannot mint the same owned token/clip identities.
    const copy = copyStashNoteAsSpokenV2(source,
      `${document.id}:${expectedRevision}:${source.id}:inline:${target.id}:${target.version}:${command.beforeTokenId}`);
    const spliced = spliceSpokenStashNoteV2(target, copy, command.beforeTokenId);
    if ("error" in spliced) return refused(document, "STASH_NOTE_INSERT_INVALID", spliced.error);
    const newIds = copy.tokens.map((token) => token.id);
    let picture: { id: string; payload: NarratedVisualPayloadV2; version: number } | undefined;
    if (source.attachedFootage) {
      if (!presentAttachedFootageForSortingV2(copy)) {
        return refused(document, "STASH_ATTACHMENT_VISUAL_CONFLICT", "The attached footage needs one unambiguous source slot and quiet or muted audio.");
      }
      const slot = copy.primaryVisualSequence?.slots[0];
      if (!slot || slot.kind !== "content" || slot.payload.kind !== "visual") {
        return refused(document, "STASH_ATTACHMENT_VISUAL_CONFLICT", "The note's attached footage could not be represented as a placed visual.");
      }
      picture = { id: slot.id, payload: slot.payload, version: slot.version };
      newIds.push(slot.id, slot.payload.payloadId);
    }
    const reserved = documentUuids(document);
    if (new Set(newIds.map((id) => id.toLowerCase())).size !== newIds.length ||
      newIds.some((id) => reserved.has(id.toLowerCase()))) {
      return refused(document, "STASH_WORD_ID_DUPLICATE", "A copied word or visual identity already belongs to another document entity.");
    }
    // Inline Stash insertion preserves every receiver token ID; none are reshaped.
    const coverage = reconcileNarrationTextCoverageV2(target, spliced.row, new Map());
    if (isCoverageRefusalV2(coverage)) return refused(document, coverage.code, coverage.message);
    const updated = spliced.row;
    updated.primaryVisualSequence!.slots = coverage.slots;
    if (coverage.unattachedVisuals.length) updated.unattachedVisuals = coverage.unattachedVisuals;
    else delete updated.unattachedVisuals;
    if (picture) {
      updated.unattachedVisuals = [...updated.unattachedVisuals ?? [], {
        slotId: picture.id, payload: picture.payload, version: picture.version,
      }];
      const attached = attachVisualV2(updated, picture.id, spliced.firstInsertedTokenId, spliced.firstInsertedTokenId);
      if (isCoverageRefusalV2(attached) || attached.unattached.length !== 0) {
        return refused(document, isCoverageRefusalV2(attached) ? attached.code : "STASH_ATTACHMENT_VISUAL_CONFLICT",
          isCoverageRefusalV2(attached) ? attached.message : "Adding footage would strand an existing visual.");
      }
      updated.primaryVisualSequence!.slots = attached.slots;
      updated.unattachedVisuals = (updated.unattachedVisuals ?? []).filter((item) => item.slotId !== picture.id);
      if (!updated.unattachedVisuals.length) delete updated.unattachedVisuals;
    }
    if (!sameAuthoringJsonV2(updated.primaryVisualSequence!.slots, target.primaryVisualSequence.slots)) {
      updated.primaryVisualSequence!.version += 1;
    }
    updated.version += 1;
    markStashOriginEditedV2(updated);
    blocks[index] = updated;
    const checklist = stashChecklistV2(source);
    // Once an inline occurrence exists, no reversible whole-row copy may
    // uncheck the note on return. Preserve manual history, but retire the
    // earlier automaticCopyId (if any).
    source.stashChecklist = { completed: true, manualRevision: checklist.manualRevision };
  } else if (command.kind === "restore_stash" || command.kind === "restore_stash_rows") {
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
  } else if (command.kind === "create_section") {
    const index = gapIndex(blocks, command.destination);
    // A section divider cannot be at a document edge or replace an existing divider.
    if (index === null || blocks[index - 1]?.type === "section" || blocks[index]?.type === "section" ||
      blocks[index - 1]?.id !== command.destination.afterRowId || blocks[index]?.id !== command.destination.beforeRowId) {
      return refused(document, "ROW_DESTINATION_INVALID", "Create a section only at an exact gap between two adjacent rows in one section.");
    }
    if (blocks.some((block) => block.id === command.sectionId)) {
      return refused(document, "SECTION_ID_DUPLICATE", "A new section needs an unused block ID.");
    }
    blocks.splice(index, 0, {
      type: "section", id: command.sectionId, orderKey: `section-${command.sectionId}`, title: command.title, version: 1,
    });
  } else if (command.kind === "rename_section") {
    const heading = blocks.find((block): block is Extract<Block, { type: "section" }> =>
      block.type === "section" && block.id === command.sectionId);
    if (!heading) return refused(document, "ROW_SELECTION_INVALID", "Choose an existing section heading to rename.");
    if (heading.title === command.title) return refused(document, "ROW_EDIT_NO_CHANGE", "The section already has that title.");
    if (!Number.isSafeInteger(heading.version) || heading.version >= Number.MAX_SAFE_INTEGER) {
      return refused(document, "ROW_CONTENT_INVALID", "The section version cannot advance safely.");
    }
    heading.title = command.title;
    heading.version += 1;
  } else if (command.kind === "delete_section_break") {
    const index = blocks.findIndex((block) => block.type === "section" && block.id === command.sectionId);
    if (index < 0) return refused(document, "ROW_SELECTION_INVALID", "Choose an existing script section break to delete.");
    // Removing only the heading keeps all row objects, IDs, order and attached intent.
    // The shared relationship guard below refuses any newly ambiguous audio coverage.
    blocks.splice(index, 1);
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
      const onlyCopy = rows.length === 1 && command.kind === "stash_rows" && !command.destination &&
        rows[0]?.type === "narration" && rows[0].stashOrigin?.sourceNoteRowId ? rows[0] : null;
      const source = onlyCopy ? stashRowById(working, onlyCopy.stashOrigin!.sourceNoteRowId!) : undefined;
      const reversible = onlyCopy && source?.type === "narration" && onlyCopy.stashOrigin?.returnEligible &&
        onlyCopy.stashOrigin.sourceContentStamp === stashNoteContentStampV2(source);
      if (reversible && onlyCopy && source?.type === "narration") {
        if (audioSpanTouchesRows(working, new Set([onlyCopy.id]))) {
          return refused(document, "AUDIO_REVIEW_REQUIRED", "Review the audio crossing the copied note before returning it.");
        }
        if (hasExternalRowReferences(working, onlyCopy.id) || working.activeDraft.supportingItems.some((item) =>
          supportingRows(item, blocks).has(onlyCopy.id))) {
          return refused(document, "ROW_REFERENCE_REVIEW_REQUIRED", "Review external row or visual references before removing this copy.");
        }
        blocks.splice(from, 1);
        const checklist = stashChecklistV2(source);
        if (onlyCopy.stashOrigin?.completionCaused && checklist.completed &&
          checklist.automaticCopyId === onlyCopy.id &&
          checklist.manualRevision === onlyCopy.stashOrigin.completionManualRevision) {
          source.stashChecklist = { completed: false, manualRevision: checklist.manualRevision };
        }
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
        if ((command.kind === "stash_group_rows" || !command.destination) && origin.returnEligible && ownerUnmoved && !owner.attachedFootage) {
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
      // A multi-row/grouped return, edited copy, or missing/changed source is
      // preserved as a complete saved row; its old source is never re-created.
      for (const row of ordinaryReturns) if (row.stashOrigin?.sourceNoteRowId) row.stashOrigin.returnEligible = false;
      const returnedOutline = planStashReturn(working, ordinaryReturns, outline,
        command.kind === "stash_rows" ? command.destination : undefined, command.kind === "stash_group_rows");
      if (!returnedOutline) return refused(document, "STASH_ORIGIN_DESTINATION_INVALID", "The requested Stash outline destination, return hierarchy, or attachment ownership cannot be preserved.");
      for (const row of rows) {
        if (row.type === "narration" && !row.stashOrigin?.sourceNoteRowId && !parkAttachedFootageForSortingV2(row)) {
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
  } else if (command.kind === "edit_narration_text") {
    const index = blocks.findIndex((block) => block.id === command.rowId);
    const block = blocks[index];
    if (!block) return refused(document, "ROW_NOT_FOUND", "Choose an existing active Draft narration row.");
    const restored = block.type === "visual_only" && block.clearedNarration
      ? restoreClearedNarration(block, block.clearedNarration) : null;
    if (restored && !("type" in restored)) return { ok: false, document, diagnostics: [restored] };
    const current = restored ?? block;
    if (current.type !== "narration" || current.state !== "active" || current.plainDirection === true) {
      return refused(document, "NARRATION_TEXT_TARGET_INVALID", "Only active ordinary narration rows can be edited with a text splice.");
    }
    if (!Number.isSafeInteger(current.version) || current.version === Number.MAX_SAFE_INTEGER) {
      return refused(document, "NARRATION_TEXT_REVISION_INVALID", "The narration row version cannot advance.");
    }
    const splice = spliceNarrationTextV2(current, command, {
      documentId: document.id, revision: expectedRevision, reservedIds: documentUuids(document),
    });
    if (!splice.ok) return refused(document, splice.code, splice.message);
    const wordless = splice.row.text === "" ? clearToVisualOnlyRow(current) : null;
    if (restored) {
      blocks[index] = { ...splice.row, version: current.version + 1 };
    } else if (wordless) {
      if (!("type" in wordless)) return { ok: false, document, diagnostics: [wordless] };
      blocks[index] = wordless;
    } else {
      const coverage = reconcileNarrationTextCoverageV2(current, splice.row, splice.reshapedTokenIds);
      if (isCoverageRefusalV2(coverage)) return refused(document, coverage.code, coverage.message);
      const row = { ...splice.row, version: current.version + 1,
        primaryVisualSequence: {
          ...current.primaryVisualSequence!, slots: coverage.slots,
          version: current.primaryVisualSequence!.version +
            (sameAuthoringJsonV2(coverage.slots, current.primaryVisualSequence!.slots) ? 0 : 1),
        },
      };
      if (coverage.unattachedVisuals.length > 0) row.unattachedVisuals = coverage.unattachedVisuals;
      else delete row.unattachedVisuals;
      blocks[index] = row;
    }
  } else if (command.kind === "set_stash_completion") {
    const entry = working.stashOutline?.find((candidate) => candidate.rowId === command.rowId);
    const row = stashRowById(working, command.rowId);
    if (!entry || !["note", "clip"].includes(entry.kind) ||
      !row || row.type !== "narration" && row.type !== "visual_only") {
      return refused(document, "STASH_CHECKLIST_ITEM_INVALID", "Check a saved Stash note or standalone clip, not a full saved row.");
    }
    const checklist = stashChecklistV2(row);
    if (checklist.completed === command.completed) return refused(document, "ROW_EDIT_NO_CHANGE", "The Stash checkbox already has this state.");
    if (checklist.manualRevision === Number.MAX_SAFE_INTEGER) return refused(document, "STASH_CHECKLIST_REVISION_EXHAUSTED", "Manual checkbox history cannot advance.");
    row.stashChecklist = { completed: command.completed, manualRevision: checklist.manualRevision + 1 };
  } else if (command.kind === "rename_visual_placement") {
    const row = [...blocks, ...(working.stash ?? []).flatMap((bundle) => bundle.rows)]
      .find((item): item is NarrationBlockV2 | VisualOnlyBlockV2 =>
        item.id === command.rowId && (item.type === "narration" || item.type === "visual_only"));
    if (!row) return refused(document, "ROW_NOT_FOUND", "Choose an existing visual row in Draft or Stash.");
    const candidates = rowVisualPlacements(row).filter((item) => item.payloadId === command.payloadId);
    if (candidates.length !== 1) return refused(document, "VISUAL_NOT_FOUND", "Choose exactly one visual placement in this row.");
    const payload = candidates[0]!;
    if (payload.pictureKind !== "clip" && payload.pictureKind !== "image") {
      return refused(document, "VISUAL_RENAME_UNSUPPORTED", "Only Footage and Still Image placements can have custom names.");
    }
    const name = command.name.trim();
    if ((payload.displayName ?? "") === name) return refused(document, "ROW_EDIT_NO_CHANGE", "This placement already has that name.");
    if (name) payload.displayName = name;
    else delete payload.displayName;
    // Attached footage has one visible mirrored slot and one owned source payload.
    // Keep both names aligned without touching the source's media reference.
    const attached = row.type === "narration" ? row.attachedFootage : undefined;
    if (row.type === "narration" && attached &&
      row.primaryVisualSequence?.slots.some((slot) => slot.kind === "content" && slot.payload === payload &&
        payload.payloadId === attachedVisualPayloadId(row.id, attached.clip.id, slot.id))) {
      if (name) attached.clip.payload.displayName = name;
      else delete attached.clip.payload.displayName;
    }
    markStashOriginEditedV2(row);
  } else if (command.kind === "delete_row_audio_span") {
    const spanIndex = working.rowAudioSpans?.findIndex((span) => span.id === command.cueId) ?? -1;
    if (spanIndex < 0) return refused(document, "MUSIC_CUE_NOT_FOUND", "Choose an existing music cue to remove.");
    const matched = [...blocks, ...(working.stash ?? []).flatMap((bundle) => bundle.rows)].flatMap((block) => {
      if (block.type !== "visual_only") return [];
      const visuals = [
        { payload: block.payload, visualOnlyTiming: block.visualOnlyTiming },
        ...(block.additionalVisuals ?? []),
      ];
      return visuals.some((visual) => visual.visualOnlyTiming.matchAudioDuration?.cueId === command.cueId)
        ? [{ block, visuals }] : [];
    });
    if (matched.some(({ block }) => block.version === Number.MAX_SAFE_INTEGER)) {
      return refused(document, "ROW_CONTENT_INVALID", "A matched visual row cannot advance its version safely.");
    }
    working.rowAudioSpans!.splice(spanIndex, 1);
    if (working.rowAudioSpans!.length === 0) delete working.rowAudioSpans;
    for (const { block, visuals } of matched) {
      let restored = false;
      for (const visual of visuals) {
        if (visual.visualOnlyTiming.matchAudioDuration?.cueId !== command.cueId) continue;
        const restoredMilliseconds = visual.visualOnlyTiming.durationOverrideMs ?? 4000;
        visual.visualOnlyTiming = { kind: "visual_only", durationOverrideMs: restoredMilliseconds };
        operationDiagnostics.push({
          ...diagnostic("VISUAL_AUDIO_MATCH_CLEARED", `Removed the music cue; restored the fixed hold of ${(restoredMilliseconds / 1000).toFixed(3).replace(/0+$/, "").replace(/\.$/, "")} s.`),
          severity: "warning",
          blockId: block.id,
          entityId: visual.payload.payloadId,
        });
        restored = true;
      }
      if (!restored) continue;
      const [first, ...rest] = visuals;
      block.payload = first!.payload;
      block.visualOnlyTiming = first!.visualOnlyTiming;
      if (rest.length > 0) block.additionalVisuals = rest as NonNullable<VisualOnlyBlockV2["additionalVisuals"]>;
      block.version += 1;
      markStashOriginEditedV2(block);
    }
  } else if (command.kind === "add_visual_to_wordless_row") {
    const reserved = documentUuids(document);
    if (reserved.has(command.payloadId.toLowerCase()) || reserved.has(command.slotId.toLowerCase()) ||
        command.payloadId.toLowerCase() === command.slotId.toLowerCase()) {
      return refused(document, "VISUAL_ID_DUPLICATE", "Use fresh and distinct picture and slot identities.");
    }
    const index = blocks.findIndex((item) => item.id === command.rowId);
    const row = blocks[index];
    if (row?.type === "visual_only") {
      const issue = appendWordlessV2(row, newWordlessPlaceholderV2(command.payloadId, command.visualType), command.slotId, 1, projectHoldMs);
      if (issue) return refused(document, issue.code, issue.message);
      markStashOriginEditedV2(row);
    } else if (row?.type === "narration") {
      const conversion = promoteWordlessNarrationV2(row, newWordlessPlaceholderV2(command.payloadId, command.visualType), command.slotId);
      if (!("value" in conversion)) return refused(document, conversion.code, conversion.message);
      blocks[index] = conversion.value;
      markStashOriginEditedV2(conversion.value);
    } else return refused(document, "ROW_NOT_FOUND", "Choose an existing wordless Draft row.");
  } else if (command.kind === "move_wordless_visual") {
    if (command.sourceRowId === command.destinationRowId) return refused(document, "CROSS_ROW_REQUIRED", "Use Reorder for visuals in the same row.");
    const source = blocks.find((item): item is VisualOnlyBlockV2 => item.type === "visual_only" && item.id === command.sourceRowId);
    const destinationIndex = blocks.findIndex((item) => item.id === command.destinationRowId);
    const target = blocks[destinationIndex];
    if (!source || !target || target.type === "section" || target.type === "direction") {
      return refused(document, "MOVE_DESTINATION_MISSING", "Choose an existing wordless source and Draft destination row.");
    }
    const reserved = documentUuids(document);
    if (command.replacementPayloadId && reserved.has(command.replacementPayloadId.toLowerCase()) ||
        command.destinationSlotId && reserved.has(command.destinationSlotId.toLowerCase()) ||
        command.replacementPayloadId && command.replacementPayloadId.toLowerCase() === command.destinationSlotId?.toLowerCase()) {
      return refused(document, "VISUAL_ID_DUPLICATE", "A fresh slot or replacement must not reuse an existing document identity.");
    }
    const destSequence = target.type === "narration" ? target.primaryVisualSequence : undefined;
    if (destSequence && command.expectedDestinationSequenceVersion !== destSequence.version) {
      return refused(document, "SEQUENCE_VERSION_STALE", "The destination picture sequence has changed.");
    }
    if (!destSequence && command.expectedDestinationSequenceVersion !== undefined) {
      return refused(document, "ROW_COMMAND_INVALID", "A wordless destination has no narrated sequence version.");
    }
    const original = wordlessPlacementsV2(source).find((entry) => entry.payload.payloadId === command.payloadId);
    if (!original) return refused(document, "VISUAL_NOT_FOUND", "The picture was not found in its source row.");
    if (target.type === "narration" && spokenTokensV2(target).length > 0) {
      if (!destSequence || destSequence.version === Number.MAX_SAFE_INTEGER || target.version === Number.MAX_SAFE_INTEGER || target.state !== "active" || target.plainDirection) {
        return refused(document, "MOVE_DESTINATION_UNSAFE", "Choose an active narrated destination with a current picture sequence.");
      }
      const conversion = toNarratedPlacementV2(original);
      if (!("value" in conversion)) return refused(document, conversion.code, conversion.message);
      const mapped = source.clearedNarration?.slots.find((slot) => slot.visualId === command.payloadId);
      if (!mapped && !command.destinationSlotId) return refused(document, "WORDLESS_DESTINATION_SLOT_REQUIRED", "Provide a fresh slot ID to attach this picture to narration later.");
      if (mapped && command.destinationSlotId) return refused(document, "ROW_COMMAND_INVALID", "Keep the picture's original narration slot rather than minting another.");
      const slotId = mapped?.id ?? command.destinationSlotId!;
      const taken = liftWordlessV2(source, command.payloadId, command.replacementPayloadId);
      if (!("value" in taken)) return refused(document, taken.code, taken.message);
      target.unattachedVisuals = [...(target.unattachedVisuals ?? []), { slotId, payload: conversion.value, version: mapped ? mapped.version + 1 : 1 }];
      destSequence.version += 1;
      target.version += 1;
    } else if (target.type === "visual_only" || target.type === "narration") {
      if (target.type === "narration" && !command.destinationSlotId && !source.clearedNarration?.slots.some((item) => item.visualId === command.payloadId)) {
        return refused(document, "WORDLESS_DESTINATION_SLOT_REQUIRED", "Provide a fresh slot ID for the receiving blank row.");
      }
      const mapped = source.clearedNarration?.slots.find((item) => item.visualId === command.payloadId);
      const slotId = mapped?.id ?? command.destinationSlotId ?? "";
      const placement = preserveWordlessHoldV2(original, defaultWordlessHoldV2(source, projectHoldMs));
      // Verify the destination before lifting. A refused move must leave the source untouched.
      if (target.type === "narration") {
        const promoted = promoteWordlessNarrationV2(target, placement, slotId, mapped ? mapped.version + 1 : 1);
        if (!("value" in promoted)) return refused(document, promoted.code, promoted.message);
        const taken = liftWordlessV2(source, command.payloadId, command.replacementPayloadId);
        if (!("value" in taken)) return refused(document, taken.code, taken.message);
        blocks[destinationIndex] = promoted.value;
      } else {
        if (target.clearedNarration && !slotId) {
          return refused(document, "WORDLESS_DESTINATION_SLOT_REQUIRED", "Provide a unique slot ID to preserve cleared narration.");
        }
        const preview = structuredClone(target);
        const issue = appendWordlessV2(preview, placement, slotId, mapped ? mapped.version + 1 : 1, projectHoldMs);
        if (issue) return refused(document, issue.code, issue.message);
        const taken = liftWordlessV2(source, command.payloadId, command.replacementPayloadId);
        if (!("value" in taken)) return refused(document, taken.code, taken.message);
        Object.assign(target, preview);
      }
    } else return refused(document, "MOVE_DESTINATION_UNSAFE", "The receiving row must be a visual or ordinary narration row.");
    markStashOriginEditedV2(source);
    const changedTarget = blocks[destinationIndex];
    if (changedTarget && changedTarget.type !== "section") markStashOriginEditedV2(changedTarget);
  } else if (command.kind === "reorder_visual_only" || command.kind === "set_visual_only_hold" || command.kind === "set_visual_only_audio_match") {
    const candidates = command.kind === "set_visual_only_audio_match" && command.cueId === null
      ? [...blocks, ...(working.stash ?? []).flatMap((bundle) => bundle.rows)]
      : blocks;
    const row = candidates.find((item): item is VisualOnlyBlockV2 => item.type === "visual_only" && item.id === command.rowId);
    if (!row) return refused(document, "ROW_NOT_FOUND", "Choose an existing visuals-only Draft row.");
    if (row.version === Number.MAX_SAFE_INTEGER) return refused(document, "ROW_CONTENT_INVALID", "The visual row version cannot advance safely.");
    const visuals = [
      { payload: row.payload, visualOnlyTiming: row.visualOnlyTiming, ...(row.researchClip ? { researchClip: row.researchClip } : {}), ...(row.frameBinding ? { frameBinding: row.frameBinding } : {}) },
      ...row.additionalVisuals ?? [],
    ];
    if (command.kind === "reorder_visual_only") {
      const oldIds = visuals.map((item) => item.payload.payloadId);
      if (command.payloadIds.length !== oldIds.length || new Set(command.payloadIds).size !== oldIds.length ||
        command.payloadIds.some((id) => !oldIds.includes(id))) {
        return refused(document, "VISUAL_ORDER_INVALID", "Choose every existing visual exactly once; no visual may be lost or added.");
      }
      if (command.payloadIds.every((id, index) => id === oldIds[index])) return refused(document, "ROW_EDIT_NO_CHANGE", "The visuals already have this order.");
      const ordered = command.payloadIds.map((id) => visuals.find((item) => item.payload.payloadId === id)!);
      const [first, ...rest] = ordered;
      row.payload = first!.payload;
      row.visualOnlyTiming = first!.visualOnlyTiming;
      if (first!.researchClip) row.researchClip = first!.researchClip; else delete row.researchClip;
      if (first!.frameBinding) row.frameBinding = first!.frameBinding; else delete row.frameBinding;
      row.additionalVisuals = rest as NonNullable<VisualOnlyBlockV2["additionalVisuals"]>;
    } else if (command.kind === "set_visual_only_hold") {
      const milliseconds = command.holdSeconds * 1000;
      if (!Number.isFinite(milliseconds) || milliseconds <= 0 || !Number.isSafeInteger(milliseconds)) {
        return refused(document, "VISUAL_HOLD_INVALID", "Hold must be a positive number of seconds, precise to one millisecond (for example 4.0 or 2.5).");
      }
      const target = visuals.find((item) => item.payload.payloadId === command.payloadId);
      if (!target) return refused(document, "VISUAL_NOT_FOUND", "Choose an existing visual in this row.");
      if (target.payload.pictureKind === "clip" || target.visualOnlyTiming.selectedSourceRange) {
        return refused(document, "VISUAL_HOLD_INVALID", "Only a still or other untimed visual can have an editable hold; clips use their trimmed length.");
      }
      if (target.visualOnlyTiming.matchAudioDuration) {
        return refused(document, "VISUAL_HOLD_MATCHED", "This visual follows its matched music cue; clear Match audio duration before editing its fixed hold.");
      }
      if (target.visualOnlyTiming.durationOverrideMs === milliseconds) return refused(document, "ROW_EDIT_NO_CHANGE", "This visual already has that hold.");
      target.visualOnlyTiming = { kind: "visual_only", durationOverrideMs: milliseconds };
      row.visualOnlyTiming = visuals[0]!.visualOnlyTiming;
      if (visuals.length > 1) row.additionalVisuals = visuals.slice(1) as NonNullable<VisualOnlyBlockV2["additionalVisuals"]>;
    } else {
      const target = visuals.find((item) => item.payload.payloadId === command.payloadId);
      if (!target) return refused(document, "VISUAL_NOT_FOUND", "Choose an existing visual in this row.");
      if (target.payload.pictureKind === "clip" || target.payload.pictureKind === "unresolved_visual") {
        return refused(document, "VISUAL_AUDIO_MATCH_UNSUPPORTED", "Only a still or other untimed visual can match a music cue; clips use their trimmed length.");
      }
      if (command.cueId === null) {
        if (!target.visualOnlyTiming.matchAudioDuration) return refused(document, "ROW_EDIT_NO_CHANGE", "This visual is not matched to a music cue.");
        const restoredMilliseconds = target.visualOnlyTiming.durationOverrideMs ?? 4000;
        target.visualOnlyTiming = {
          kind: "visual_only",
          durationOverrideMs: restoredMilliseconds,
        };
        operationDiagnostics = [{
          ...diagnostic("VISUAL_AUDIO_MATCH_CLEARED", `Match audio duration was cleared; restored the fixed hold of ${(restoredMilliseconds / 1000).toFixed(3).replace(/0+$/, "").replace(/\.$/, "")} s.`),
          severity: "warning",
          blockId: row.id,
          entityId: target.payload.payloadId,
        }];
      } else {
        const span = working.rowAudioSpans?.find((item) => item.id === command.cueId);
        const sourceIn = span?.timing?.sourceInFrame;
        const sourceOut = span?.timing?.sourceOutFrame;
        if (sourceIn === undefined || sourceOut === undefined || sourceOut <= sourceIn) {
          return refused(document, "VISUAL_AUDIO_MATCH_INVALID", "Choose a saved music cue with fixed source in and out points.");
        }
        if (target.visualOnlyTiming.matchAudioDuration?.cueId === command.cueId) {
          return refused(document, "ROW_EDIT_NO_CHANGE", "This visual already matches that music cue.");
        }
        target.visualOnlyTiming = {
          ...target.visualOnlyTiming,
          durationOverrideMs: target.visualOnlyTiming.durationOverrideMs ?? 4000,
          matchAudioDuration: { cueId: command.cueId },
        };
      }
      row.visualOnlyTiming = visuals[0]!.visualOnlyTiming;
      if (visuals.length > 1) row.additionalVisuals = visuals.slice(1) as NonNullable<VisualOnlyBlockV2["additionalVisuals"]>;
    }
    row.version += 1;
    markStashOriginEditedV2(row);
  } else if (command.kind === "edit_row") {
    const index = blocks.findIndex((block) => block.type !== "section" && block.id === command.rowId);
    if (index < 0) return refused(document, "ROW_NOT_FOUND", "Choose an existing Draft or Stash row to edit.");
    const current = blocks[index] as Row;
    let replacement: Row;
    try { replacement = structuredClone(command.row); }
    catch { return refused(document, "ROW_CONTENT_INVALID", "The edited row must be losslessly representable as valid saved JSON."); }
    if (replacement.id !== current.id || replacement.type !== current.type) return refused(document, "ROW_IDENTITY_INVALID", "An authored row edit must preserve the row's existing ID and type.");
    if (current.type === "visual_only" && replacement.type === "visual_only" &&
      !sameAuthoringJsonV2(current.clearedNarration, replacement.clearedNarration)) {
      return refused(document, "ROW_CONTENT_INVALID", "Only a narration text edit can change whether a row contains cleared narration.");
    }
    if (current.type === "narration" && replacement.type === "narration" && current.plainDirection !== replacement.plainDirection) {
      return refused(document, "ROW_CONTENT_INVALID", "Use explicit Make spoken or Make stage direction to change plain-note speech intent.");
    }
    if (current.type === "narration" && replacement.type === "narration" &&
      !sameAuthoringJsonV2(current.attachedFootage, replacement.attachedFootage)) {
      return refused(document, "STASH_ATTACHMENT_REVIEW_REQUIRED", "Use explicit footage commands to change an attached clip.");
    }
    if (!sameAuthoringJsonV2("stashChecklist" in current ? current.stashChecklist : undefined,
      "stashChecklist" in replacement ? replacement.stashChecklist : undefined)) {
      return refused(document, "STASH_CHECKLIST_COMMAND_REQUIRED", "Checkbox changes require the dedicated Stash completion command.");
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
    // New authored still cards start at D146's four-second hold. Never migrate
    // historical single-visual rows or change their frozen default/goldens.
    if (row.type === "visual_only") {
      for (const visual of [row, ...row.additionalVisuals ?? []]) {
        if (visual.payload.pictureKind !== "clip" && visual.payload.pictureKind !== "unresolved_visual" &&
          visual.visualOnlyTiming.durationOverrideMs === undefined) {
          visual.visualOnlyTiming.durationOverrideMs = NEW_VISUAL_HOLD_MS;
        }
      }
    }
    blocks.splice(index, 0, row);
    moved = [row];
  } else if (command.kind === "delete_rows") {
    const deleted = deleteRows(working, command.rowIds);
    if ("code" in deleted) return { ok: false, document, diagnostics: [deleted] };
    moved = deleted.rows;
  } else if (command.kind === "split_row" || command.kind === "join_rows") {
    // Word identities, visuals and row references are settled inside; any refusal discards the clone.
    const problem = applySplitOrJoinV2(working, command);
    if (problem) return { ok: false, document, diagnostics: [problem] };
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
      const destination = attachmentCommand.destination;
      const parentId = destination ? destination.parentRowId : note.id;
      const sectionId = destination ? destination.sectionId : noteEntry.sectionId;
      let at = entries.findIndex((entry) => entry.rowId === note.id) + 1;
      if (destination) {
        const siblings = entries.filter((entry) => entry.parentRowId === parentId && entry.sectionId === sectionId);
        const after = destination.afterRowId === null ? -1 : siblings.findIndex((entry) => entry.rowId === destination.afterRowId);
        const before = siblings[after + 1]?.rowId ?? null;
        if (!sectionExists(working, sectionId) || (parentId !== null && !entries.some((entry) =>
          entry.rowId === parentId && entry.kind === "note" && entry.sectionId === sectionId)) ||
          destination.afterRowId !== null && after < 0 || before !== destination.beforeRowId) {
          return refused(document, "STASH_OUTLINE_SLOT_INVALID", "Choose a current exact Stash location for the detached footage.");
        }
        at = destination.beforeRowId !== null && destination.afterRowId === null
          ? entries.findIndex((entry) => entry.rowId === destination.beforeRowId)
          : outlineInsertionIndex(working, entries, parentId, sectionId, destination.afterRowId)!;
      }
      if (!releaseAttachedClip(working, note.id, attachmentCommand.bundleId, parentId, sectionId, at)) {
        return refused(document, "STASH_ATTACHMENT_BUNDLE_INVALID", "Choose an unused bundle ID for the detached footage.");
      }
    } else {
      const noteSlot = note.primaryVisualSequence?.slots.length === 1 ? note.primaryVisualSequence.slots[0] : undefined;
      const clearingText = attachmentCommand.clearText === true;
      if (!note.attachedFootage || note.plainDirection !== true ||
        (!clearingText && (note.text.trim() !== "" || note.tokens.length !== 0)) || note.overlayEvents.length !== 0 ||
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
  } else if (command.kind === "rename_stash_section") {
    const section = working.stashSections?.find((item) => item.id === command.sectionId);
    if (!section) return refused(document, "STASH_SECTION_NOT_FOUND", "Choose an existing Stash section.");
    // Rename only the heading; legacy rowIds are intentionally left untouched.
    section.title = command.title;
  } else if (command.kind === "delete_stash_section") {
    const sectionIndex = working.stashSections?.findIndex((item) => item.id === command.sectionId) ?? -1;
    if (sectionIndex < 0) return refused(document, "STASH_SECTION_NOT_FOUND", "Choose an existing Stash section.");
    const hasLegacyRows = working.stashSections![sectionIndex]!.rowIds.length > 0;
    const hasCanonicalRows = working.stashOutline?.some((entry) => entry.sectionId === command.sectionId) ?? false;
    if (hasLegacyRows || hasCanonicalRows) {
      // Upgrade before removing the legacy section so its membership is not lost.
      const entries = ensureStashOutline(working);
      const promoted = entries.filter((entry) => entry.sectionId === command.sectionId)
        .map((entry) => ({ ...entry, sectionId: null }));
      const remaining = entries.filter((entry) => entry.sectionId !== command.sectionId);
      // A single contiguous preorder block at the very top of unsorted.
      working.stashOutline = [...promoted, ...remaining];
    }
    working.stashSections!.splice(sectionIndex, 1);
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
    if (command.kind === "create_stash_clip" && Object.hasOwn(command, "atStart") &&
        (command.atStart !== true || command.afterRowId !== null)) {
      return refused(document, "STASH_OUTLINE_SLOT_INVALID", "Choose an exact start or sibling position.");
    }
    const first = command.kind === "create_stash_clip" && command.atStart
      ? entries.findIndex((entry) => entry.parentRowId === command.parentRowId && entry.sectionId === command.sectionId) : -1;
    const insertAt = first >= 0 ? first :
      outlineInsertionIndex(working, entries, command.parentRowId, command.sectionId, command.afterRowId);
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
      row.stashChecklist = { completed: false, manualRevision: 0 };
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
      row.stashChecklist = { completed: false, manualRevision: 0 };
      kind = "clip";
    }
    entries.splice(insertAt, 0, { rowId: row.id, kind, parentRowId: command.parentRowId, sectionId: command.sectionId });
    (working.stash ??= []).push({ id: command.bundleId, rows: [row], supportingItems: [] });
  } else if (command.kind === "stash_visual") {
    const text = (value: unknown): value is string => typeof value === "string" && value.length > 0;
    const place = (value: unknown): value is string | null => value === null || text(value);
    if (!isJsonValue(command) ||
      !exactKeys(command, ["kind", "rowId", "slotId", "bundleId", "stashRowId", "sectionId", "parentRowId", "afterRowId"]) ||
      !text(command.rowId) || !text(command.slotId) || !text(command.bundleId) || !text(command.stashRowId) ||
      !place(command.sectionId) || !place(command.parentRowId) || !place(command.afterRowId)) {
      return refused(document, "ROW_COMMAND_INVALID", "Provide the row, the visual, new Stash IDs and an exact Stash outline location.");
    }
    const row = blocks.find((block): block is NarrationBlockV2 => block.type === "narration" && block.id === command.rowId);
    if (!row) return refused(document, "ROW_SELECTION_INVALID", "Choose a visual in a script row with narration to stash.");
    if ((working.stash ?? []).some((bundle) => bundle.id === command.bundleId)) return refused(document, "ROW_COMMAND_INVALID", "Provide an unused Stash bundle ID.");
    if (blocks.some((block) => block.id === command.stashRowId) || stashRowById(working, command.stashRowId)) return refused(document, "ROW_ID_DUPLICATE", "A stashed visual needs a new saved-row ID.");
    ensureStashOutline(working);
    const entries = working.stashOutline!;
    if (!sectionExists(working, command.sectionId)) return refused(document, "STASH_SECTION_NOT_FOUND", "Choose an existing Stash section or the unsectioned Stash area.");
    if (command.parentRowId !== null) {
      const parent = entries.find((entry) => entry.rowId === command.parentRowId);
      if (!parent || parent.kind !== "note" || parent.sectionId !== command.sectionId) return refused(document, "STASH_OUTLINE_PARENT_INVALID", "Nest an item under a saved note in the same Stash section.");
    }
    const insertAt = outlineInsertionIndex(working, entries, command.parentRowId, command.sectionId, command.afterRowId);
    if (insertAt === null) return refused(document, "STASH_OUTLINE_SLOT_INVALID", "Choose a current sibling in the same Stash outline location.");
    const lifted = liftVisualV2(row, command.slotId, "stashed");
    if (isCoverageRefusalV2(lifted)) return { ok: false, document, diagnostics: [{ ...diagnostic(lifted.code, lifted.message), blockId: row.id, entityId: lifted.entityId ?? command.slotId }] };
    const visual = lifted.payload;
    if (visual.researchStill || visual.researchQuotePicture) {
      return refused(document, "WORDLESS_RESEARCH_STILL_UNSUPPORTED",
        "Stash the whole row to keep this Research picture's saved-copy provenance.");
    }
    const footage = visual.pictureKind === "clip";
    if (footage && !visual.selectedSourceRange) {
      return refused(document, "STASH_VISUAL_TRIM_REQUIRED", "This footage has an in-point but no chosen length, so Stash cannot keep its trim. Trim it in the row first, then stash it.");
    }
    const clip: VisualOnlyBlockV2 = {
      type: "visual_only", id: command.stashRowId, orderKey: row.orderKey, version: 1,
      payload: {
        kind: "visual", payloadId: visual.payloadId, pictureKind: visual.pictureKind, source: visual.source,
        audioPolicy: visual.audioPolicy,
        ...(visual.framingPolicy !== undefined ? { framingPolicy: visual.framingPolicy } : {}),
        ...(visual.imageMotion !== undefined ? { imageMotion: visual.imageMotion } : {}),
        ...(visual.displayName !== undefined ? { displayName: visual.displayName } : {}),
      },
      visualOnlyTiming: { kind: "visual_only", ...(footage ? { selectedSourceRange: visual.selectedSourceRange! } : {}) },
      ...(visual.researchClip ? { researchClip: visual.researchClip } : {}),
      ...(visual.frameBinding ? { frameBinding: visual.frameBinding } : {}),
    };
    // Footage arrives as a compact Stash clip; any other visual is an ordinary saved row holding that one picture.
    const compact = footage || visual.pictureKind === "unresolved_visual" && visual.researchClip !== undefined && visual.frameBinding === undefined;
    markStashOriginEditedV2(row);
    entries.splice(insertAt, 0, { rowId: clip.id, kind: compact ? "clip" : "row", parentRowId: command.parentRowId, sectionId: command.sectionId });
    (working.stash ??= []).push({ id: command.bundleId, rows: [clip], supportingItems: [] });
  } else if (command.kind === "insert_stash_visual") {
    if (!exactKeys(command, ["kind", "stashRowId", "destinationRowId", "destinationSlotId"]) ||
      !uuid(command.stashRowId) || !uuid(command.destinationRowId) || !uuid(command.destinationSlotId)) {
      return refused(document, "ROW_COMMAND_INVALID", "Choose a saved visual, receiving row and a fresh visual slot.");
    }
    const target = blocks.find((row): row is NarrationBlockV2 =>
      row.type === "narration" && row.id === command.destinationRowId);
    const sequence = target?.primaryVisualSequence;
    if (!target || !sequence || target.state !== "active" || target.plainDirection || !spokenTokensV2(target).length ||
      target.version === Number.MAX_SAFE_INTEGER || sequence.version === Number.MAX_SAFE_INTEGER) {
      return refused(document, "MOVE_DESTINATION_UNSAFE", "Choose an active row with spoken words to receive this visual.");
    }
    if (documentUuids(document).has(command.destinationSlotId.toLowerCase())) {
      return refused(document, "VISUAL_ID_DUPLICATE", "Choose a new visual slot.");
    }
    ensureStashOutline(working);
    const source = stashRowById(working, command.stashRowId);
    if (source?.type !== "visual_only" || source.clearedNarration || source.additionalVisuals?.length ||
      (working.stashGroups ?? []).some((group) => group.rowIds.includes(command.stashRowId))) {
      return refused(document, "STASH_VISUAL_UNAVAILABLE", "Choose a single ungrouped stashed visual.");
    }
    const converted = toNarratedPlacementV2(wordlessPlacementsV2(source)[0]!);
    if (!("value" in converted)) return refused(document, converted.code, converted.message);
    if (!removeOrdinaryStashClip(working, command.stashRowId, true)) {
      return refused(document, "STASH_VISUAL_UNAVAILABLE", "This visual has saved references that require restoring its whole row.");
    }
    target.unattachedVisuals = [...(target.unattachedVisuals ?? []), {
      slotId: command.destinationSlotId, payload: converted.value, version: 1,
    }];
    sequence.version += 1;
    target.version += 1;
    markStashOriginEditedV2(target);
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
    const requested = command.includeDescendants === false ? subtree.filter((entry) => command.rowIds.includes(entry.rowId)) : subtree;
    // Place ignores completed descendants and checked standalone clips even when
    // Hide completed is off. An explicitly selected completed note remains a
    // deliberate whole-note copy (S03-STASH-020).
    const eligible = requested.filter((entry) => {
      const row = stashRowById(working, entry.rowId);
      return row && (!stashChecklistV2(row).completed || entry.kind === "note" && command.rowIds.includes(entry.rowId));
    });
    if (eligible.length === 0) return refused(document, "STASH_NOTHING_TO_PLACE", "There is no unfinished Stash material to place in the script.");
    const moving = new Set(eligible.filter((entry) => entry.kind !== "note").map((entry) => entry.rowId));
    for (const group of working.stashGroups ?? []) {
      if (!group.rowIds.some((rowId) => moving.has(rowId))) continue;
      if (group.rowIds.some((rowId) => command.rowIds.includes(rowId)) ||
          !group.rowIds.every((rowId) => moving.has(rowId))) {
        return refused(document, "STASH_GROUP_ATOMIC_REQUIRED", "Place all rows of a Stash group together.");
      }
      removeGroup(working, group.id);
    }
    const origins = new Map<string, StashOriginV2>();
    for (const entry of eligible) {
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
    const copies = new Map<string, NarrationBlockV2>();
    for (const [ordinal, entry] of eligible.entries()) {
      const row = stashRowById(working, entry.rowId);
      if (entry.kind === "note") {
        if (row?.type !== "narration") return refused(document, "STASH_NOTE_CONTENT_INVALID", "A saved note must contain a narration row.");
        const checklist = stashChecklistV2(row);
        const copied = copyStashNoteAsSpokenV2(row, `${document.id}:${expectedRevision}:${entry.rowId}:${ordinal}`);
        const firstCheck = !checklist.completed;
        copied.stashOrigin = {
          ...origins.get(entry.rowId)!,
          sourceNoteRowId: row.id,
          sourceContentStamp: stashNoteContentStampV2(row),
          completionCaused: firstCheck,
          completionManualRevision: checklist.manualRevision,
        };
        if (!presentAttachedFootageForSortingV2(copied)) {
          return refused(document, "STASH_ATTACHMENT_VISUAL_CONFLICT", "The copied note needs one safe visual slot for its owned footage.");
        }
        if (firstCheck) row.stashChecklist = {
          completed: true, manualRevision: checklist.manualRevision, automaticCopyId: copied.id,
        };
        copies.set(row.id, copied);
      } else if (row) {
        row.stashOrigin = origins.get(entry.rowId)!;
        if (row.type === "visual_only") delete row.stashChecklist;
        if (row.type === "narration" && !presentAttachedFootageForSortingV2(row)) {
          return refused(document, "STASH_ATTACHMENT_VISUAL_CONFLICT", "The note needs an unambiguous primary visual slot and footage with an explicitly muted or quiet source-audio policy.");
        }
      }
    }
    if (command.includeDescendants === false) {
      // Keep ordinary children in Stash and promote only direct children of moved roots.
      for (const entry of entries) {
        if (entry.parentRowId !== null && moving.has(entry.parentRowId)) {
          entry.parentRowId = origins.get(entry.parentRowId)!.parentRowId;
        }
      }
    }
    const stashOrder = stashRowsInVisibleOrder(working).map((row) => row.id);
    const taken = moving.size ? takeStashRows(working, moving, stashOrder) : { rows: [] as Row[] };
    if ("code" in taken) return { ok: false, document, diagnostics: [taken] };
    const movedById = new Map(taken.rows.map((row) => [row.id, row]));
    moved = eligible.flatMap((entry) => {
      const row = copies.get(entry.rowId) ?? movedById.get(entry.rowId);
      return row ? [row] : [];
    });
    placementCounts = {
      copiedNotes: copies.size,
      movedClips: eligible.filter((entry) => entry.kind === "clip").length,
      movedSavedRows: eligible.filter((entry) => entry.kind === "row").length,
      skippedCompleted: requested.length - eligible.length,
      attachedFootageCopies: [...copies.values()].filter((row) => !!row.attachedFootage).length,
    };
    blocks.splice(index, 0, ...moved);
  } else return refused(document, "ROW_COMMAND_INVALID", "Unknown row edit command.");
  if (working.stashSections?.length === 0) delete working.stashSections;
  if (working.stashOutline?.length === 0 && !working.stashSections?.length) delete working.stashOutline;
  if (working.stash?.length === 0 && document.stash === undefined) delete working.stash;
  if (JSON.stringify(working) === JSON.stringify(document)) return refused(document, "ROW_EDIT_NO_CHANGE", "The edit would leave Stash and Draft unchanged.");
  // A split or join has already moved each transition and music cue to the row that holds its words.
  const relationshipProblem = command.kind === "split_row" || command.kind === "join_rows"
    ? null
    : updateRelationships(document, working, command, new Set(moved.map((row) => row.id)));
  if (relationshipProblem) return { ok: false, document, diagnostics: [relationshipProblem] };
  working.rowEditRevision = expectedRevision + 1;
  invalidateChangedStashSourceLinksV2(document, working);
  const after = validateScriptDocumentV2(working);
  const signature = (document: ScriptDocumentV2, item: AuthoringDiagnosticV2) => {
    if (item.code === "MUSIC_MATCH_INVALID") return JSON.stringify([item.code, item.blockId, item.entityId, item.message]);
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
  if (command.kind === "edit_row" || command.kind === "edit_narration_text" || command.kind === "stash_selected_words" || command.kind === "insert_stash_note_words" || command.kind === "rename_visual_placement" || command.kind === "reorder_visual_only" || command.kind === "set_visual_only_hold" || command.kind === "set_visual_only_audio_match" || command.kind === "add_visual_to_wordless_row" || command.kind === "move_wordless_visual" || command.kind === "delete_row_audio_span" || command.kind === "create_row" || command.kind === "delete_rows" || command.kind === "save_stash_group" ||
    command.kind === "split_row" || command.kind === "join_rows" || command.kind === "create_section" ||
    command.kind === "rename_section" || command.kind === "delete_section_break") {
    const saved = serializedDocument(working);
    return saved
      ? { ok: true, document: saved, diagnostics: operationDiagnostics }
      : refused(document, "ROW_CONTENT_INVALID", "The row edit must be losslessly representable as valid saved JSON.");
  }
  return { ok: true, document: working, diagnostics: [], ...(placementCounts ? { placementCounts } : {}) };
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
  // A stale match is recoverable authoring state after concurrent cue removal;
  // retain it for an explicit clear and let the compiler refuse to guess.
  const fatal = validation.diagnostics.filter((item) => ["SCHEMA_INVALID", "ENTITY_ID_DUPLICATE", "BLOCK_ID_DUPLICATE", "ROW_REFERENCE_INVALID", "PLAIN_DIRECTION_INTENT_INVALID", "FOOTAGE_OWNER_DUPLICATE", "RESEARCH_CLIP_INVALID", "STASH_GROUP_INVALID", "CLEARED_NARRATION_INVALID", "QUOTE_BOX_TEXT_INVALID", "QUOTE_BOX_ITALIC_SPAN_INVALID"].includes(item.code));
  return fatal.length ? { ok: false, diagnostics: fatal } : { ok: true, document: document as ScriptDocumentV2 };
}

/** Session-owned history is independent of consumer views; no collaborative undo is implied. */
export function createRowEditSessionV2(initial: ScriptDocumentV2, projectHoldMs = LEGACY_VISUAL_HOLD_MS) {
  let current = structuredClone(initial);
  let revision = current.rowEditRevision ?? 0;
  const history: ScriptDocumentV2[] = [];
  const redoHistory: ScriptDocumentV2[] = [];
  /**
   * D124: the split this session made last, while nothing has changed since.
   * Every edit and every Undo advances the revision, so one number proves that.
   */
  let lastSplit: { revision: number; before: ScriptDocumentV2; rowIds: [string, string] } | null = null;
  return {
    get document() { return structuredClone(current); },
    get revision() { return revision; },
    get undoDepth() { return history.length; },
    get redoDepth() { return redoHistory.length; },
    view(kind: "script" | "outline" | "stash") {
      if (kind === "stash") return structuredClone(current.stash ?? []);
      return structuredClone(kind === "outline" ? current.activeDraft.blocks.filter((block) => block.type === "section") : current.activeDraft.blocks);
    },
    apply(command: RowEditCommandV2, expectedRevision = revision): RowEditResultV2 {
      if (expectedRevision !== revision) return refused(structuredClone(current), "ROW_REVISION_STALE", "The session changed before this edit.");
      const split = lastSplit;
      if (split && split.revision === revision && revision !== Number.MAX_SAFE_INTEGER &&
        isSplitOrJoinCommandV2(command) && command.kind === "join_rows" && joinReversesSplitV2(current, command, split.rowIds)) {
        // Joining the two halves straight back restores the row exactly as it was before the
        // split: clipped visuals get their words back and no paragraph break is added. It is
        // still one edit, so Undo returns to the split rows.
        lastSplit = null;
        history.push(current);
        redoHistory.length = 0;
        revision++;
        current = { ...structuredClone(split.before), rowEditRevision: revision };
        return { ok: true, document: structuredClone(current), diagnostics: [] };
      }
      const result = applyRowEditV2(current, current.rowEditRevision ?? 0, command, projectHoldMs);
      if (result.ok) {
        lastSplit = command.kind === "split_row"
          ? { revision: revision + 1, before: current, rowIds: [command.rowId, command.newRowId] }
          : null;
        history.push(current); current = result.document; revision++;
        redoHistory.length = 0;
      }
      return { ...result, document: structuredClone(result.document) };
    },
    /**
     * Visual edits share the row history. A confirmed range change and all its
     * fallout (neighbouring ranges, On Camera passages, framing, returns, card
     * order) are exactly one entry; a refused edit adds none.
     */
    applyVisualEdit(command: VisualSequenceEditCommandV2, expectedRevision = revision): VisualSequenceEditResultV2 {
      if (expectedRevision !== revision || revision === Number.MAX_SAFE_INTEGER) {
        return refused(structuredClone(current), "ROW_REVISION_STALE", "The session changed before this edit, or its revision cannot advance.");
      }
      const blockId = command.kind === "move_payload" ? command.sourceBlockId : command.blockId;
      const row = current.activeDraft.blocks.find((block) => block.id === blockId);
      const sequenceVersion = row?.type === "narration" ? row.primaryVisualSequence?.version ?? 0 : 0;
      const result = applyVisualSequenceEditV2(current, sequenceVersion, command, projectHoldMs);
      if (!result.ok) return { ...result, document: structuredClone(current) };
      history.push(current);
      redoHistory.length = 0;
      revision++;
      current = { ...result.document, rowEditRevision: revision };
      return { ...result, document: structuredClone(current) };
    },
    undo(): RowEditResultV2 {
      if (revision === Number.MAX_SAFE_INTEGER) return refused(structuredClone(current), "ROW_REVISION_STALE", "The session revision cannot advance.");
      const previous = history.pop();
      if (!previous) return refused(structuredClone(current), "ROW_UNDO_EMPTY", "There is no row transaction to undo.");
      redoHistory.push(current);
      lastSplit = null;
      revision++;
      current = { ...previous, rowEditRevision: revision };
      return { ok: true, document: structuredClone(current), diagnostics: [] };
    },
    redo(): RowEditResultV2 {
      if (revision === Number.MAX_SAFE_INTEGER) return refused(structuredClone(current), "ROW_REVISION_STALE", "The session revision cannot advance.");
      const next = redoHistory.pop();
      if (!next) return refused(structuredClone(current), "ROW_REDO_EMPTY", "There is no row transaction to redo.");
      history.push(current);
      lastSplit = null;
      revision++;
      current = { ...next, rowEditRevision: revision };
      return { ok: true, document: structuredClone(current), diagnostics: [] };
    },
  };
}
