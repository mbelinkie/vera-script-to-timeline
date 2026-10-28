import type { ScriptDocumentV2 } from "./generated/contracts-v2.js";
import { sameAuthoringJsonV2 as sameJson } from "./authoring-v2-json.js";
import { createSortingProjectionV2, updateSortingProjectionV2, projectSortingDocumentV2 } from "./authoring-v2-sorting-projection.js";
import { resolveSortingCommentsV2, type SortingCommentContextV2 } from "./authoring-v2-sorting-comments.js";
import type { CommentStateV2 } from "./authoring-v2-comments.js";
import {
  createRowEditSessionV2,
  deserializeAuthoringDocumentV2,
  serializeAuthoringDocumentV2,
  type RowEditCommandV2,
  type RowEditResultV2,
} from "./authoring-v2-rows.js";

const MAX_EDITS = 1000;
const MAX_SAVED_CHARACTERS = 5_000_000;
type Action = RowEditCommandV2 | { kind: "undo" };
type Phase = "sorting" | "preview" | "accepted" | "discarded";
export type SortingAcceptanceV2 = "all" | "edits_only" | "sorting_only";
export type SortingResultV2 = RowEditResultV2 & { changed: boolean; comments?: CommentStateV2 };

interface Position { container: string; index: number; beforeSections: string[]; sectionId?: string | null }
function positions(document: ScriptDocumentV2): Map<string, Position> {
  const result = new Map<string, Position>();
  let sectionId: string | null = null;
  let beforeSections: string[] = [];
  let index = 0;
  for (const block of document.activeDraft.blocks) {
    if (block.type === "section") {
      sectionId = block.id;
      beforeSections = [...beforeSections, block.id];
      index = 0;
    } else {
      result.set(block.id, { container: `draft:${sectionId ?? ""}`, index: index++, beforeSections, sectionId });
    }
  }
  const stashRows = (document.stash ?? []).flatMap((bundle) => bundle.rows);
  if (document.stashOutline) {
    for (const entry of document.stashOutline) {
      const index = document.stashOutline.filter((item) => item.parentRowId === entry.parentRowId && item.sectionId === entry.sectionId && document.stashOutline!.indexOf(item) < document.stashOutline!.indexOf(entry)).length;
      result.set(entry.rowId, { container: `stash:${entry.sectionId ?? ""}:${entry.parentRowId ?? ""}`, index, beforeSections: [], sectionId: entry.sectionId });
    }
  } else {
    const sectioned = new Set((document.stashSections ?? []).flatMap((section) => section.rowIds));
    stashRows.filter((row) => !sectioned.has(row.id)).forEach((row, index) => result.set(row.id, { container: "stash::", index, beforeSections: [], sectionId: null }));
    for (const section of document.stashSections ?? []) {
      section.rowIds.forEach((rowId, index) => result.set(rowId, { container: `stash:${section.id}:`, index, beforeSections: [], sectionId: section.id }));
    }
  }
  return result;
}

function selectedOutlineRows(document: ScriptDocumentV2, roots: string[]): string[] {
  if (!document.stashOutline) return roots;
  const byId = new Map(document.stashOutline.map((entry) => [entry.rowId, entry]));
  const selectedRoots = new Set(roots);
  const descendant = (rowId: string, root: string): boolean => {
    let parent = byId.get(rowId)?.parentRowId ?? null;
    while (parent !== null) {
      if (parent === root) return true;
      parent = byId.get(parent)?.parentRowId ?? null;
    }
    return false;
  };
  return document.stashOutline.filter((entry) => selectedRoots.has(entry.rowId) || roots.some((root) => descendant(entry.rowId, root))).map((entry) => entry.rowId);
}

function originalRowPositions(baseline: Map<string, Position>, containers: Map<string, string[]>, current: Map<string, Position>): Set<string> {
  const result = new Set<string>();
  for (const [container, ids] of containers) {
    const present = ids.filter((id) => current.get(id)?.container === container);
    const first = present[0];
    if (!first || !sameJson(baseline.get(first)!.beforeSections, current.get(first)!.beforeSections)) continue;
    // Prefix maxima and suffix minima compare relative order once per container.
    const suffixMin: number[] = [];
    let minimum = Infinity;
    for (let index = present.length - 1; index >= 0; index--) {
      suffixMin[index] = minimum;
      minimum = Math.min(minimum, current.get(present[index]!)!.index);
    }
    let maximum = -1;
    present.forEach((id, index) => {
      const position = current.get(id)!.index;
      if (maximum < position && position < suffixMin[index]!) result.add(id);
      maximum = Math.max(maximum, position);
    });
  }
  return result;
}

function commandAllowed(command: unknown): command is RowEditCommandV2 {
  if (!command || typeof command !== "object" || Array.isArray(command)) return false;
  const keys: Record<string, string[]> = {
    move_rows: ["kind", "rowIds", "destination"],
    move_section: ["kind", "sectionId", "destination"],
    stash_rows: ["kind", "rowIds", "bundleId"],
    restore_stash: ["kind", "bundleId", "destination"],
    restore_stash_rows: ["kind", "rowIds", "destination"],
    create_stash_section: ["kind", "sectionId", "title"],
    move_stash_rows: ["kind", "rowIds", "sectionId"],
    set_stash_outline: ["kind", "entries"],
    place_stash_rows: ["kind", "rowIds", "destination"],
    edit_row: ["kind", "rowId", "row"],
    create_row: ["kind", "row", "destination"],
    delete_rows: ["kind", "rowIds"],
    create_stash_note: ["kind", "bundleId", "row", "sectionId", "parentRowId", "afterRowId"],
    create_stash_clip: ["kind", "bundleId", "row", "sectionId", "parentRowId", "afterRowId"],
    make_stage_direction: ["kind", "blockId", "startOffset", "endOffset"],
    make_spoken: ["kind", "blockId", "startOffset", "endOffset"],
    delete_direction_delimiter: ["kind", "blockId", "offset"],
  };
  const kind = (command as { kind: string }).kind;
  const allowed = Object.hasOwn(keys, kind) ? keys[kind] : undefined;
  const value = command as Record<string, unknown>;
  const optional = kind === "create_stash_note" ? ["mode"] : [];
  if (!allowed || !allowed.every((key) => Object.hasOwn(value, key)) || !Object.keys(value).every((key) => allowed.includes(key) || optional.includes(key))) return false;
  if ("row" in value && (!value.row || typeof value.row !== "object" || Array.isArray(value.row))) return false;
  if (kind === "edit_row") return typeof value.rowId === "string";
  if (kind === "make_stage_direction" || kind === "make_spoken" || kind === "delete_direction_delimiter") {
    return typeof value.blockId === "string" && (kind === "delete_direction_delimiter" ? Number.isSafeInteger(value.offset) : Number.isSafeInteger(value.startOffset) && Number.isSafeInteger(value.endOffset));
  }
  if (kind === "move_rows" || kind === "stash_rows" || kind === "restore_stash_rows" || kind === "move_stash_rows" || kind === "place_stash_rows" || kind === "delete_rows") {
    if (!Array.isArray(value.rowIds) || !value.rowIds.every((id: unknown) => typeof id === "string")) return false;
  }
  if (kind === "delete_rows") return true;
  if (kind === "create_stash_note" || kind === "create_stash_clip") {
    return typeof value.bundleId === "string" && [value.sectionId, value.parentRowId, value.afterRowId].every((id) => id === null || typeof id === "string") &&
      (!Object.hasOwn(value, "mode") || value.mode === "default_direction" || value.mode === "authored");
  }
  if ((kind === "stash_rows" || kind === "restore_stash") && typeof value.bundleId !== "string") return false;
  if (kind === "move_section" && typeof value.sectionId !== "string") return false;
  if (kind === "stash_rows") return true;
  if (kind === "create_stash_section") return typeof value.sectionId === "string" && typeof value.title === "string";
  if (kind === "move_stash_rows") return value.sectionId === null || typeof value.sectionId === "string";
  if (kind === "set_stash_outline") {
    return Array.isArray(value.entries) && value.entries.every((entry: unknown) => {
      if (!entry || typeof entry !== "object" || Array.isArray(entry)) return false;
      const item = entry as Record<string, unknown>;
      return Object.keys(item).length === 4 && Object.hasOwn(item, "rowId") && Object.hasOwn(item, "kind") &&
        Object.hasOwn(item, "parentRowId") && Object.hasOwn(item, "sectionId") &&
        typeof item.rowId === "string" && ["note", "clip", "row"].includes(item.kind as string) &&
        (item.parentRowId === null || typeof item.parentRowId === "string") && (item.sectionId === null || typeof item.sectionId === "string");
    });
  }
  const gap = value.destination;
  if (!gap || typeof gap !== "object" || Array.isArray(gap)) return false;
  const gapKeys = kind === "move_section" ? ["afterSectionId", "beforeSectionId"] : ["sectionId", "afterRowId", "beforeRowId"];
  return Object.keys(gap).length === gapKeys.length && Object.entries(gap).every(([key, id]) => gapKeys.includes(key) && (id === null || typeof id === "string"));
}

/** Local trial only. The caller owns the canonical document and installs an accepted result once. */
export function createSortingTrialV2(initial: ScriptDocumentV2) {
  const baselineJson = serializeAuthoringDocumentV2(initial);
  const baseline = JSON.parse(baselineJson) as ScriptDocumentV2;
  const originalPositions = positions(baseline);
  const containers = new Map<string, string[]>();
  for (const [id, position] of originalPositions) {
    const ids = containers.get(position.container) ?? [];
    ids.push(id);
    containers.set(position.container, ids);
  }
  const session = createRowEditSessionV2(baseline);
  let projection = createSortingProjectionV2(baseline);
  const projectionHistory: typeof projection[] = [];
  const actions: Action[] = [];
  const markHistory: Set<string>[] = [];
  let movedRows = new Set<string>();
  let phase: Phase = "sorting";
  let finalDocument: ScriptDocumentV2 | undefined;
  const failure = (code: string, message: string, document = finalDocument ? structuredClone(finalDocument) : session.document): RowEditResultV2 => ({
    ok: false, document, diagnostics: [{ code, message, jsonPath: "/activeDraft" }],
  });
  const pending = () => phase === "sorting" || phase === "preview";
  const trial = {
    get phase() { return phase; },
    get document() { return finalDocument ? structuredClone(finalDocument) : session.document; },
    get undoDepth() { return pending() ? session.undoDepth : 0; },
    get revision() { return finalDocument ? finalDocument.rowEditRevision ?? 0 : session.revision; },
    get movedRowIds() {
      if (!pending()) return [];
      return [...movedRows];
    },
    preview(): ScriptDocumentV2 {
      if (!pending()) throw new Error("The Sorting trial is closed.");
      phase = "preview";
      return session.document;
    },
    returnToSorting(): boolean {
      if (!pending()) return false;
      phase = "sorting";
      return true;
    },
    apply(command: RowEditCommandV2, expectedRevision = session.revision): RowEditResultV2 {
      if (phase !== "sorting") return failure("SORTING_READ_ONLY", "Return to Sorting before changing trial order.");
      if (!commandAllowed(command)) return failure("SORTING_COMMAND_INVALID", "Provide a supported, complete row authoring or organization command.");
      if ((command.kind === "create_row" || command.kind === "create_stash_note" || command.kind === "create_stash_clip") &&
        (originalPositions.has(command.row.id) || projection.births.some((birth) => birth.rowId === command.row.id))) {
        return failure("SORTING_ROW_ID_REUSED", "Create material with a fresh row identity; use Undo to restore a deleted row.");
      }
      if (actions.filter((action) => action.kind !== "undo").length >= MAX_EDITS) return failure("SORTING_TRIAL_LIMIT", "Finish this bounded trial before adding more operations.");
      const beforeDocument = session.document;
      const before = positions(beforeDocument);
      const selected = command.kind === "move_rows" || command.kind === "stash_rows" || command.kind === "restore_stash_rows" || command.kind === "move_stash_rows" ? command.rowIds
        : command.kind === "place_stash_rows" ? selectedOutlineRows(beforeDocument, command.rowIds)
          : command.kind === "set_stash_outline" ? beforeDocument.stashOutline ? beforeDocument.stashOutline.flatMap((entry) => {
            const next = command.entries.find((item) => item.rowId === entry.rowId);
            return next && (next.kind !== entry.kind || next.parentRowId !== entry.parentRowId || next.sectionId !== entry.sectionId || beforeDocument.stashOutline!.findIndex((item) => item.rowId === entry.rowId) !== command.entries.findIndex((item) => item.rowId === entry.rowId)) ? [entry.rowId] : [];
          }) : command.entries.map((entry) => entry.rowId)
          : command.kind === "restore_stash" ? beforeDocument.stash?.find((bundle) => bundle.id === command.bundleId)?.rows.map((row) => row.id) ?? []
            : command.kind === "move_section" ? [...before].filter(([, location]) => location.sectionId === command.sectionId).map(([id]) => id)
              : [];
      const result = session.apply(command, expectedRevision);
      if (result.ok) {
        projectionHistory.push(projection);
        projection = updateSortingProjectionV2(projection, beforeDocument, result.document, command);
        actions.push(structuredClone(command));
        markHistory.push(movedRows);
        const current = positions(result.document);
        const unchanged = originalRowPositions(originalPositions, containers, current);
        // Only deliberately selected rows get marks; rows displaced by them do not.
        movedRows = new Set([...movedRows, ...selected].filter((id) => !unchanged.has(id)));
      }
      return result;
    },
    undo(): RowEditResultV2 {
      if (phase !== "sorting") return failure("SORTING_READ_ONLY", "Return to Sorting before undoing a trial operation.");
      const result = session.undo();
      if (result.ok) { actions.push({ kind: "undo" }); movedRows = markHistory.pop()!; projection = projectionHistory.pop()!; }
      return result;
    },
    accept(canonical: ScriptDocumentV2, outcome: SortingAcceptanceV2 = "all", comments?: SortingCommentContextV2): SortingResultV2 {
      if (!pending()) return { ...failure("SORTING_TRIAL_CLOSED", "This trial has already been accepted or discarded.", canonical), changed: false };
      if (!sameJson(canonical, baseline)) return { ...failure("SORTING_BASELINE_CHANGED", "The saved script or Stash changed. Start a new trial from that document.", canonical), changed: false };
      if (!["all", "edits_only", "sorting_only"].includes(outcome)) return { ...failure("SORTING_OUTCOME_INVALID", "Choose all changes, edits only, or sorting only.", canonical), changed: false };
      const projected = outcome === "all" ? { ok: true, document: session.document, diagnostics: [] } : projectSortingDocumentV2(projection, session.document, outcome);
      if (!projected.ok) return { ...projected, document: canonical, changed: false };
      const intended = projected.document;
      const content = (document: ScriptDocumentV2) => {
        const copy = { ...document };
        delete copy.rowEditRevision;
        if (copy.stash?.length === 0) delete copy.stash;
        return copy;
      };
      const changed = !sameJson(content(intended), content(baseline));
      if (changed && (baseline.rowEditRevision ?? 0) === Number.MAX_SAFE_INTEGER) return { ...failure("ROW_REVISION_STALE", "The document revision cannot advance.", canonical), changed: false };
      const document = changed ? { ...intended, rowEditRevision: (baseline.rowEditRevision ?? 0) + 1 } : canonical;
      const discussion = comments ? resolveSortingCommentsV2(canonical, document, comments) : undefined;
      if (discussion && !discussion.ok) return { ...failure("SORTING_COMMENTS_INVALID", discussion.error, canonical), changed: false };
      phase = "accepted";
      finalDocument = structuredClone(document);
      return { ok: true, document, diagnostics: [], changed, ...(discussion?.ok ? { comments: discussion.state } : {}) };
    },
    discard(canonical: ScriptDocumentV2, comments?: SortingCommentContextV2): RowEditResultV2 & { comments?: CommentStateV2 } {
      if (!pending()) return failure("SORTING_TRIAL_CLOSED", "This trial has already been accepted or discarded.", canonical);
      const discussion = comments ? resolveSortingCommentsV2(canonical, canonical, comments) : undefined;
      if (discussion && !discussion.ok) return failure("SORTING_COMMENTS_INVALID", discussion.error, canonical);
      phase = "discarded";
      finalDocument = structuredClone(canonical);
      return { ok: true, document: canonical, diagnostics: [], ...(discussion?.ok ? { comments: discussion.state } : {}) };
    },
    serialize(): string {
      if (!pending()) throw new Error("Only a pending Sorting trial can be saved.");
      const json = JSON.stringify({ format: "sorting-trial/v1", baseline, actions, phase });
      if (json.length > MAX_SAVED_CHARACTERS) throw new Error("The saved Sorting trial exceeds the bounded local size limit.");
      return json;
    },
  };
  return trial;
}

/** Replay complete public operations so local Undo and projection provenance survive reload. */
export function resumeSortingTrialV2(json: string): ReturnType<typeof createSortingTrialV2> {
  if (json.length > MAX_SAVED_CHARACTERS) throw new Error("The saved Sorting trial exceeds the bounded local size limit.");
  const saved = JSON.parse(json) as { format: string; baseline: ScriptDocumentV2; actions: Action[]; phase: Phase };
  if (!saved || saved.format !== "sorting-trial/v1" || !Array.isArray(saved.actions) || saved.actions.length > MAX_EDITS * 2 || !["sorting", "preview"].includes(saved.phase)) throw new Error("Invalid saved Sorting trial.");
  const loaded = deserializeAuthoringDocumentV2(JSON.stringify(saved.baseline));
  if (!loaded.ok) throw new Error("Invalid Sorting baseline.");
  const trial = createSortingTrialV2(loaded.document);
  for (const action of saved.actions) {
    const result = action && action.kind === "undo" && Object.keys(action).length === 1 ? trial.undo() : trial.apply(action as RowEditCommandV2);
    if (!result.ok) throw new Error(`Invalid saved Sorting operation: ${result.diagnostics.map((item) => item.code).join(", ")}`);
  }
  if (saved.phase === "preview") trial.preview();
  return trial;
}
