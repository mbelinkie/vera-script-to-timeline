import type { NarrationBlockV2, ScriptDocumentV2 } from "./generated/contracts-v2.js";
import type { AuthoringDiagnosticV2 } from "./authoring-v2.js";
import { validateScriptDocumentV2 } from "./authoring-v2-validation.js";
import { inspectStageDirectionsV2 } from "./authoring-v2-stage-directions.js";

export type StageDirectionEditCommandV2 =
  | { kind: "make_stage_direction" | "make_spoken"; blockId: string; startOffset: number; endOffset: number }
  | { kind: "delete_direction_delimiter"; blockId: string; offset: number };

export interface StageDirectionUndoV2 {
  expectedBlockVersion: number;
  /** Exact prior row state; Undo restores literal brackets and all row attachments too. */
  rowSnapshot: NarrationBlockV2;
}

export interface StageDirectionEditResultV2 {
  ok: boolean;
  document: ScriptDocumentV2;
  diagnostics: AuthoringDiagnosticV2[];
  undo?: StageDirectionUndoV2;
}

type Row = ScriptDocumentV2["activeDraft"]["blocks"][number];

interface RowLocation {
  row: NarrationBlockV2;
  stashed: boolean;
}

function diagnostic(code: string, message: string, blockId?: string): AuthoringDiagnosticV2 {
  return { code, message, jsonPath: blockId ? `/activeDraft/blocks/${blockId}` : "/activeDraft/blocks", ...(blockId ? { blockId } : {}) };
}

function failure(document: ScriptDocumentV2, code: string, message: string, blockId?: string): StageDirectionEditResultV2 {
  return { ok: false, document, diagnostics: [diagnostic(code, message, blockId)] };
}

function locateRow(document: ScriptDocumentV2, blockId: string): RowLocation | null {
  const active = document.activeDraft.blocks.find((block) => block.id === blockId);
  if (active?.type === "narration") return { row: active, stashed: false };
  for (const bundle of document.stash ?? []) {
    const row = bundle.rows.find((item) => item.id === blockId);
    if (row?.type === "narration") return { row, stashed: true };
  }
  return null;
}

function selectedTokens(row: NarrationBlockV2, startOffset: number, endOffset: number): {
  startIndex: number;
  endIndexExclusive: number;
  hasPair: boolean;
} | null {
  if (!Number.isSafeInteger(startOffset) || !Number.isSafeInteger(endOffset) || startOffset < 0 || endOffset <= startOffset || endOffset > row.text.length) return null;
  const hasPair = row.text[startOffset] === "[" && row.text[endOffset - 1] === "]";
  const contentStart = startOffset + (hasPair ? 1 : 0);
  const contentEnd = endOffset - (hasPair ? 1 : 0);
  if (contentStart >= contentEnd) return null;
  const startIndex = row.tokens.findIndex((token) => token.startOffset === contentStart);
  const endIndex = row.tokens.findIndex((token) => token.endOffset === contentEnd);
  if (startIndex < 0 || endIndex < startIndex) return null;
  if (row.tokens.slice(startIndex, endIndex + 1).some((token) => token.startOffset < contentStart || token.endOffset > contentEnd)) return null;
  if (/[\[\]]/u.test(row.text.slice(contentStart, contentEnd))) return null;
  return { startIndex, endIndexExclusive: endIndex + 1, hasPair };
}

function selectedDirectionRun(
  row: NarrationBlockV2,
  startOffset: number,
  endOffset: number,
): ReturnType<typeof selectedTokens> {
  const selection = selectedTokens(row, startOffset, endOffset);
  if (!selection) return null;
  const { runs } = inspectStageDirectionsV2(row);
  return runs.some((run) => run.startTokenIndex === selection.startIndex && run.endTokenIndexExclusive === selection.endIndexExclusive)
    ? selection
    : null;
}

function refreshTextRangeQuotes(value: unknown, row: NarrationBlockV2): void {
  if (!value || typeof value !== "object") return;
  if (Array.isArray(value)) {
    value.forEach((child) => refreshTextRangeQuotes(child, row));
    return;
  }
  const item = value as Record<string, unknown>;
  if (
    item.blockId === row.id && typeof item.startTokenId === "string" && typeof item.endTokenId === "string" &&
    (item.startAffinity === "before" || item.startAffinity === "after") &&
    (item.endAffinity === "before" || item.endAffinity === "after")
  ) {
    const start = row.tokens.find((token) => token.id === item.startTokenId);
    const end = row.tokens.find((token) => token.id === item.endTokenId);
    if (start && end) {
      const from = item.startAffinity === "before" ? start.startOffset : start.endOffset;
      const to = item.endAffinity === "before" ? end.startOffset : end.endOffset;
      if (from < to) item.quotedText = row.text.slice(from, to);
    }
  }
  Object.values(item).forEach((child) => refreshTextRangeQuotes(child, row));
}

function insertMarkers(row: NarrationBlockV2, startIndex: number, endIndexExclusive: number): void {
  const start = row.tokens[startIndex]!.startOffset;
  const end = row.tokens[endIndexExclusive - 1]!.endOffset;
  row.text = `${row.text.slice(0, start)}[${row.text.slice(start, end)}]${row.text.slice(end)}`;
  for (const token of row.tokens) {
    const oldStart = token.startOffset;
    const oldEnd = token.endOffset;
    token.startOffset += Number(oldStart >= start) + Number(oldStart >= end);
    token.endOffset += Number(oldEnd > start) + Number(oldEnd > end);
  }
  for (let index = startIndex; index < endIndexExclusive; index += 1) row.tokens[index]!.spoken = false;
}

function removeMarkers(row: NarrationBlockV2, startIndex: number, endIndexExclusive: number, openOffset: number, closeOffset: number): void {
  row.text = `${row.text.slice(0, openOffset)}${row.text.slice(openOffset + 1, closeOffset)}${row.text.slice(closeOffset + 1)}`;
  for (const token of row.tokens) {
    const oldStart = token.startOffset;
    const oldEnd = token.endOffset;
    token.startOffset -= Number(oldStart > openOffset) + Number(oldStart > closeOffset);
    token.endOffset -= Number(oldEnd > openOffset) + Number(oldEnd > closeOffset);
  }
  for (let index = startIndex; index < endIndexExclusive; index += 1) delete row.tokens[index]!.spoken;
}

/** Apply one exact, immutable text classification edit to an active or saved Stash narration row. */
export function applyStageDirectionEditV2(
  document: ScriptDocumentV2,
  expectedBlockVersion: number,
  command: StageDirectionEditCommandV2,
): StageDirectionEditResultV2 {
  const before = validateScriptDocumentV2(document);
  if (!before.valid) return { ok: false, document, diagnostics: before.diagnostics };
  if (!command || typeof command !== "object" || typeof command.blockId !== "string") {
    return failure(document, "STAGE_DIRECTION_COMMAND_INVALID", "Provide a stage-direction text edit.");
  }
  const location = locateRow(document, command.blockId);
  if (!location) return failure(document, "STAGE_DIRECTION_ROW_MISSING", "Choose an existing narration row in the script or Stash.", command.blockId);
  if (!Number.isSafeInteger(expectedBlockVersion) || expectedBlockVersion !== location.row.version || expectedBlockVersion === Number.MAX_SAFE_INTEGER) {
    return failure(document, "STAGE_DIRECTION_VERSION_STALE", "The narration row changed before this text edit, or its version cannot advance.", command.blockId);
  }

  const working = structuredClone(document);
  const workingLocation = locateRow(working, command.blockId)!;
  const row = workingLocation.row;
  const rowSnapshot = structuredClone(row);
  const stageBefore = inspectStageDirectionsV2(row);
  if (stageBefore.issues.length > 0) return failure(document, "STAGE_DIRECTION_PAIR_INVALID", stageBefore.issues[0]!.message, command.blockId);
  let startIndex: number;
  let endIndexExclusive: number;
  if (command.kind === "delete_direction_delimiter") {
    if (!Number.isSafeInteger(command.offset) || command.offset < 0 || command.offset >= row.text.length) return failure(document, "STAGE_DIRECTION_SELECTION_INVALID", "Select one delimiter of a recognized stage-direction pair.", command.blockId);
    const run = stageBefore.runs.find((candidate) => candidate.openOffset === command.offset || candidate.closeOffset === command.offset);
    if (!run) return failure(document, "STAGE_DIRECTION_PAIR_NOT_FOUND", "Only a delimiter of a recognized complete pair can be deleted by this operation.", command.blockId);
    startIndex = run.startTokenIndex;
    endIndexExclusive = run.endTokenIndexExclusive;
    removeMarkers(row, startIndex, endIndexExclusive, run.openOffset, run.closeOffset);
  } else {
    const selection = selectedTokens(row, command.startOffset, command.endOffset);
    if (!selection) return failure(document, "STAGE_DIRECTION_SELECTION_INVALID", "Select a nonempty range aligned to whole current text tokens.", command.blockId);
    startIndex = selection.startIndex;
    endIndexExclusive = selection.endIndexExclusive;
    if (command.kind === "make_stage_direction") {
      if (row.tokens.slice(startIndex, endIndexExclusive).some((token) => token.spoken === false)) return failure(document, "STAGE_DIRECTION_SELECTION_INVALID", "The selected range already contains stage-direction text.", command.blockId);
      if (selection.hasPair) {
        // A complete pasted pair is classified only when explicitly selected and converted.
        for (let index = startIndex; index < endIndexExclusive; index += 1) row.tokens[index]!.spoken = false;
      } else {
        insertMarkers(row, startIndex, endIndexExclusive);
      }
    } else if (command.kind === "make_spoken") {
      const selectionWithMarkers = selectedDirectionRun(row, command.startOffset, command.endOffset);
      const selectedIds = new Set(row.tokens.slice(startIndex, endIndexExclusive).map((token) => token.id));
      const run = stageBefore.runs.find((candidate) => candidate.startTokenIndex === startIndex && candidate.endTokenIndexExclusive === endIndexExclusive);
      const selectedRun = run ?? (selectionWithMarkers ? stageBefore.runs.find((candidate) => candidate.startTokenIndex === startIndex && candidate.endTokenIndexExclusive === endIndexExclusive) : undefined);
      if (!selectedRun || row.tokens.slice(startIndex, endIndexExclusive).some((token) => token.spoken !== false) || selectedIds.size !== endIndexExclusive - startIndex) return failure(document, "STAGE_DIRECTION_SELECTION_INVALID", "Make spoken must select one whole recognized direction range.", command.blockId);
      removeMarkers(row, startIndex, endIndexExclusive, selectedRun.openOffset, selectedRun.closeOffset);
    } else {
      return failure(document, "STAGE_DIRECTION_COMMAND_INVALID", "Unknown stage-direction text edit.", command.blockId);
    }
  }

  if (row.version >= Number.MAX_SAFE_INTEGER) return failure(document, "STAGE_DIRECTION_VERSION_STALE", "The narration row version cannot advance.", command.blockId);
  row.version += 1;
  refreshTextRangeQuotes(working, row);
  if (workingLocation.stashed) {
    const revision = working.rowEditRevision ?? 0;
    if (!Number.isSafeInteger(revision) || revision >= Number.MAX_SAFE_INTEGER) return failure(document, "STAGE_DIRECTION_VERSION_STALE", "The saved row revision cannot advance.", command.blockId);
    working.rowEditRevision = revision + 1;
  }
  const after = validateScriptDocumentV2(working);
  if (!after.valid) return { ok: false, document, diagnostics: after.diagnostics };
  return {
    ok: true,
    document: working,
    diagnostics: [],
    undo: { expectedBlockVersion: row.version, rowSnapshot },
  };
}

/** Restore the exact prior row returned with a successful edit; stale history refuses atomically. */
export function undoStageDirectionEditV2(
  document: ScriptDocumentV2,
  undo: StageDirectionUndoV2,
): StageDirectionEditResultV2 {
  if (!undo || typeof undo !== "object") return failure(document, "STAGE_DIRECTION_UNDO_INVALID", "Provide a stage-direction Undo record.");
  const before = validateScriptDocumentV2(document);
  if (!before.valid) return { ok: false, document, diagnostics: before.diagnostics };
  const snapshot = undo.rowSnapshot;
  if (!snapshot || snapshot.type !== "narration" || typeof snapshot.id !== "string") {
    return failure(document, "STAGE_DIRECTION_UNDO_INVALID", "The Undo record has no prior narration row state.");
  }
  const location = locateRow(document, snapshot.id);
  if (!location) return failure(document, "STAGE_DIRECTION_ROW_MISSING", "The narration row changed before Undo.", snapshot.id);
  if (!Number.isSafeInteger(undo.expectedBlockVersion) || undo.expectedBlockVersion !== location.row.version || location.row.version >= Number.MAX_SAFE_INTEGER) {
    return failure(document, "STAGE_DIRECTION_VERSION_STALE", "The narration row changed after this text edit, or its version cannot advance.", snapshot.id);
  }

  const working = structuredClone(document);
  const workingLocation = locateRow(working, snapshot.id)!;
  const expectedBlockVersion = workingLocation.row.version + 1;
  const restored = structuredClone(snapshot);
  restored.version = expectedBlockVersion;
  if (workingLocation.stashed) {
    const bundle = working.stash?.find((item) => item.rows.some((row) => row.id === snapshot.id));
    if (!bundle) return failure(document, "STAGE_DIRECTION_ROW_MISSING", "The saved narration row changed before Undo.", snapshot.id);
    const index = bundle.rows.findIndex((row) => row.id === snapshot.id);
    if (index < 0) return failure(document, "STAGE_DIRECTION_ROW_MISSING", "The saved narration row changed before Undo.", snapshot.id);
    bundle.rows[index] = restored;
    const revision = working.rowEditRevision ?? 0;
    if (!Number.isSafeInteger(revision) || revision >= Number.MAX_SAFE_INTEGER) return failure(document, "STAGE_DIRECTION_VERSION_STALE", "The saved row revision cannot advance.", snapshot.id);
    working.rowEditRevision = revision + 1;
  } else {
    const index = working.activeDraft.blocks.findIndex((row) => row.id === snapshot.id);
    if (index < 0) return failure(document, "STAGE_DIRECTION_ROW_MISSING", "The narration row changed before Undo.", snapshot.id);
    working.activeDraft.blocks[index] = restored;
  }
  refreshTextRangeQuotes(working, restored);
  const after = validateScriptDocumentV2(working);
  if (!after.valid) return { ok: false, document, diagnostics: after.diagnostics };
  return {
    ok: true,
    document: working,
    diagnostics: [],
    undo: { expectedBlockVersion: restored.version, rowSnapshot: structuredClone(location.row) },
  };
}
