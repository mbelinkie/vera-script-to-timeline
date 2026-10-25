import type { RowStashBundleV2, ScriptDocumentV2 } from "./generated/contracts-v2.js";
import type { AuthoringDiagnosticV2 } from "./authoring-v2.js";
import { serializeAuthoringDocumentV2, type RowEditResultV2 } from "./authoring-v2-rows.js";
import { validateScriptDocumentV2 } from "./authoring-v2-validation.js";
import { sameAuthoringJsonV2 } from "./authoring-v2-json.js";

export type StashedRowV2 = RowStashBundleV2["rows"][number];

export interface StashRowEditCommandV2 {
  bundleId: string;
  rowId: string;
  row: StashedRowV2;
}

const fatalDocumentDiagnostics = new Set([
  "SCHEMA_INVALID",
  "ENTITY_ID_DUPLICATE",
  "BLOCK_ID_DUPLICATE",
  "ROW_REFERENCE_INVALID",
]);

const diagnostic = (code: string, message: string): AuthoringDiagnosticV2 => ({
  code,
  message,
  jsonPath: "/stash",
});

const refused = (
  document: ScriptDocumentV2,
  code: string,
  message: string,
): RowEditResultV2 => ({
  ok: false,
  document,
  diagnostics: [diagnostic(code, message)],
});

/** Replace one complete saved Stash row without changing its identity or attachments. */
export function applyStashRowEditV2(
  document: ScriptDocumentV2,
  expectedRevision: number,
  command: StashRowEditCommandV2,
): RowEditResultV2 {
  if (!command || typeof command !== "object" || !command.row || typeof command.row !== "object" || Array.isArray(command.row)) {
    return refused(document, "STASH_ROW_COMMAND_INVALID", "Provide a saved row edit.");
  }

  const before = validateScriptDocumentV2(document);
  if (before.diagnostics.some((item) => fatalDocumentDiagnostics.has(item.code))) {
    return { ok: false, document, diagnostics: before.diagnostics };
  }
  if (!Number.isSafeInteger(expectedRevision) || expectedRevision !== (document.rowEditRevision ?? 0) || expectedRevision === Number.MAX_SAFE_INTEGER) {
    return refused(document, "ROW_REVISION_STALE", "The row document changed before this edit, or its revision cannot advance.");
  }

  const bundle = document.stash?.find((candidate) => candidate.id === command.bundleId);
  if (!bundle) return refused(document, "STASH_BUNDLE_NOT_FOUND", "Choose an existing saved Stash bundle.");
  const rowIndex = bundle.rows.findIndex((row) => row.id === command.rowId);
  if (rowIndex < 0) return refused(document, "STASH_ROW_NOT_FOUND", "Choose a row in the selected Stash bundle.");

  const current = bundle.rows[rowIndex]!;
  if (command.row.id !== current.id || command.row.type !== current.type) {
    return refused(document, "STASH_ROW_IDENTITY_INVALID", "A saved row edit must preserve the row's existing ID and type.");
  }

  if (sameAuthoringJsonV2(current, command.row)) {
    return refused(document, "STASH_ROW_EDIT_NO_CHANGE", "The saved row already has this content.");
  }

  let working: ScriptDocumentV2;
  try {
    working = structuredClone(document);
    const workingBundle = working.stash!.find((candidate) => candidate.id === command.bundleId)!;
    workingBundle.rows[rowIndex] = structuredClone(command.row);
    working.rowEditRevision = expectedRevision + 1;
  } catch {
    return refused(document, "STASH_ROW_JSON_INVALID", "The edited row must be losslessly representable as saved JSON.");
  }

  const after = validateScriptDocumentV2(working);
  // Draft content is untouched; parked semantic problems remain visible warnings until restore.
  const errors = after.diagnostics.filter((item) => fatalDocumentDiagnostics.has(item.code));
  if (errors.length) return { ok: false, document, diagnostics: errors };

  try {
    // The normal save boundary also rejects non-JSON values and validates the serialized document.
    const saved = serializeAuthoringDocumentV2(working);
    return { ok: true, document: JSON.parse(saved) as ScriptDocumentV2, diagnostics: [] };
  } catch {
    return refused(document, "STASH_ROW_JSON_INVALID", "The edited row must be losslessly representable as a valid saved document.");
  }
}
