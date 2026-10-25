import type { ScriptDocumentV2 } from "./generated/contracts-v2.js";
import { canonicalJson } from "./compiler-core.js";
import {
  createRowEditSessionV2,
  deserializeAuthoringDocumentV2,
  serializeAuthoringDocumentV2,
  type RowEditCommandV2,
  type RowEditResultV2,
} from "./authoring-v2-rows.js";

const MAX_ACTIONS = 1000;
const MAX_SAVED_CHARACTERS = 5_000_000;
type Action = RowEditCommandV2 | { kind: "undo" };
type Phase = "sorting" | "preview" | "accepted" | "discarded";

function positions(document: ScriptDocumentV2): Map<string, string> {
  const result = new Map<string, string>();
  let sectionId: string | null = null;
  let sectionIndex = 0;
  let index = 0;
  for (const block of document.activeDraft.blocks) {
    if (block.type === "section") {
      sectionId = block.id;
      sectionIndex++;
      index = 0;
    } else result.set(block.id, JSON.stringify(["draft", sectionId, sectionIndex, index++]));
  }
  for (const bundle of document.stash ?? []) {
    bundle.rows.forEach((row, rowIndex) => result.set(row.id, JSON.stringify(["stash", bundle.id, rowIndex])));
  }
  return result;
}

function commandAllowed(command: unknown): command is RowEditCommandV2 {
  if (!command || typeof command !== "object") return false;
  const keys: Record<string, string[]> = {
    move_rows: ["kind", "rowIds", "destination"],
    move_section: ["kind", "sectionId", "destination"],
    stash_rows: ["kind", "rowIds", "bundleId"],
    restore_stash: ["kind", "bundleId", "destination"],
  };
  const allowed = keys[(command as { kind: string }).kind];
  return !!allowed && Object.keys(command).length === allowed.length && Object.keys(command).every((key) => allowed.includes(key));
}

/** Local trial only. The caller owns the canonical document and installs an accepted result once. */
export function createSortingTrialV2(initial: ScriptDocumentV2) {
  const baselineJson = serializeAuthoringDocumentV2(initial);
  const baseline = JSON.parse(baselineJson) as ScriptDocumentV2;
  const originalPositions = positions(baseline);
  const session = createRowEditSessionV2(baseline);
  const actions: Action[] = [];
  const deliberateRows = new Set<string>();
  let phase: Phase = "sorting";
  const failure = (code: string, message: string, document = session.document): RowEditResultV2 => ({
    ok: false, document, diagnostics: [{ code, message, jsonPath: "/activeDraft" }],
  });
  const pending = () => phase === "sorting" || phase === "preview";
  const trial = {
    get phase() { return phase; },
    get document() { return session.document; },
    get undoDepth() { return session.undoDepth; },
    get revision() { return session.revision; },
    get movedRowIds() {
      const current = positions(session.document);
      return [...deliberateRows].filter((id) => originalPositions.get(id) !== current.get(id));
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
      if (!commandAllowed(command)) return failure("SORTING_CONTENT_READ_ONLY", "Only row move, Stash and restore commands are available during a trial.");
      if (actions.length >= MAX_ACTIONS) return failure("SORTING_TRIAL_LIMIT", "Save or finish this bounded trial before adding more operations.");
      const beforeDocument = session.document;
      const before = positions(beforeDocument);
      const selected = command.kind === "move_rows" || command.kind === "stash_rows" ? command.rowIds
        : command.kind === "restore_stash" ? beforeDocument.stash?.find((bundle) => bundle.id === command.bundleId)?.rows.map((row) => row.id) ?? []
        : [...before].filter(([, location]) => JSON.parse(location)[1] === command.sectionId).map(([id]) => id);
      const result = session.apply(command, expectedRevision);
      if (result.ok) {
        actions.push(structuredClone(command));
        // Only deliberately selected rows get marks; rows displaced by them do not.
        selected.forEach((id) => deliberateRows.add(id));
      }
      return result;
    },
    undo(): RowEditResultV2 {
      if (phase !== "sorting") return failure("SORTING_READ_ONLY", "Return to Sorting before undoing a trial operation.");
      if (actions.length >= MAX_ACTIONS) return failure("SORTING_TRIAL_LIMIT", "Finish this bounded trial before adding more operations.");
      const result = session.undo();
      if (result.ok) actions.push({ kind: "undo" });
      return result;
    },
    accept(canonical: ScriptDocumentV2): RowEditResultV2 & { changed: boolean } {
      if (!pending()) return { ...failure("SORTING_TRIAL_CLOSED", "This trial has already been accepted or discarded.", canonical), changed: false };
      if (canonicalJson(canonical) !== canonicalJson(baseline)) return { ...failure("SORTING_BASELINE_CHANGED", "The saved script or Stash changed. Start a new trial from that document.", canonical), changed: false };
      const intended = session.document;
      const content = (document: ScriptDocumentV2) => { const copy = { ...document }; delete copy.rowEditRevision; return canonicalJson(copy); };
      const changed = content(intended) !== content(baseline);
      if (changed && (baseline.rowEditRevision ?? 0) === Number.MAX_SAFE_INTEGER) return { ...failure("ROW_REVISION_STALE", "The document revision cannot advance.", canonical), changed: false };
      phase = "accepted";
      return { ok: true, document: changed ? { ...intended, rowEditRevision: (baseline.rowEditRevision ?? 0) + 1 } : canonical, diagnostics: [], changed };
    },
    discard(canonical: ScriptDocumentV2): RowEditResultV2 {
      if (!pending()) return failure("SORTING_TRIAL_CLOSED", "This trial has already been accepted or discarded.", canonical);
      phase = "discarded";
      return { ok: true, document: canonical, diagnostics: [] };
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

/** Replay the same public row operations; saved content cannot bypass the trial's read-only rule. */
export function resumeSortingTrialV2(json: string): ReturnType<typeof createSortingTrialV2> {
  if (json.length > MAX_SAVED_CHARACTERS) throw new Error("The saved Sorting trial exceeds the bounded local size limit.");
  const saved = JSON.parse(json) as { format: string; baseline: ScriptDocumentV2; actions: Action[]; phase: Phase };
  if (!saved || saved.format !== "sorting-trial/v1" || !Array.isArray(saved.actions) || saved.actions.length > MAX_ACTIONS || !["sorting", "preview"].includes(saved.phase)) throw new Error("Invalid saved Sorting trial.");
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
