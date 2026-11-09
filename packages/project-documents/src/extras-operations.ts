import {
  applyRowEditV2,
  serializeAuthoringDocumentV2,
  type RowEditCommandV2,
  type RowEditResultV2,
} from "@vera/contracts/authoring-v2";
import type { ScriptDocumentV2 } from "@vera/contracts/v2";
import { duplicateExtrasRows, type ExtrasDuplicateCommand } from "./extras-duplicate.js";

/** Extras currently uses the existing Stash backing store, NOT the reserved v2 extras field. */
export type ExtrasStorageCommand = Extract<RowEditCommandV2, {
  kind: "stash_rows" | "restore_stash" | "restore_stash_rows" | "place_stash_rows";
}>;

const UUID = /^[a-f\d]{8}-(?:[a-f\d]{4}-){3}[a-f\d]{12}$/iu;

function exactObject(value: unknown, keys: readonly string[], optional: readonly string[] = []): value is Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  try {
    if (Object.getPrototypeOf(value) !== Object.prototype) return false;
    const ownKeys = Reflect.ownKeys(value);
    if (ownKeys.length < keys.length || ownKeys.length > keys.length + optional.length) return false;
    if (!keys.every((key) => Object.hasOwn(value, key))) return false;
    return ownKeys.every((key) => typeof key === "string" &&
      (keys.includes(key) || optional.includes(key)) &&
      Object.getOwnPropertyDescriptor(value, key)?.enumerable === true &&
      Object.hasOwn(Object.getOwnPropertyDescriptor(value, key)!, "value"));
  } catch {
    return false;
  }
}

function uuidOrNull(value: unknown): value is string | null {
  return value === null || typeof value === "string" && UUID.test(value);
}

function rowIds(value: unknown): value is string[] {
  if (!Array.isArray(value)) return false;
  try {
    if (Object.getPrototypeOf(value) !== Array.prototype || value.length === 0 || value.length > 4096 ||
        Reflect.ownKeys(value).length !== value.length + 1) return false;
    const ids: string[] = [];
    for (let index = 0; index < value.length; index++) {
      const descriptor = Object.getOwnPropertyDescriptor(value, String(index));
      if (!descriptor?.enumerable || !Object.hasOwn(descriptor, "value") ||
          typeof descriptor.value !== "string" || !UUID.test(descriptor.value)) return false;
      ids.push(descriptor.value);
    }
    return new Set(ids).size === ids.length;
  } catch {
    return false;
  }
}

function gap(value: unknown, stashDestination = false): boolean {
  if (!exactObject(value, ["sectionId", "afterRowId", "beforeRowId"], stashDestination ? ["parentRowId"] : [])) return false;
  if (!uuidOrNull(value.sectionId) || !uuidOrNull(value.afterRowId) || !uuidOrNull(value.beforeRowId)) return false;
  if (value.afterRowId !== null && value.afterRowId === value.beforeRowId) return false;
  return !stashDestination || (Object.hasOwn(value, "parentRowId") && uuidOrNull(value.parentRowId));
}

/** Strict JSON-shape allowlist for the four currently supported whole-row operations. */
export function parseExtrasStorageCommand(value: unknown): ExtrasStorageCommand | null {
  if (!exactObject(value, ["kind"], ["rowIds", "bundleId", "destination", "includeDescendants"])) return null;
  switch (value.kind) {
    case "stash_rows":
      return exactObject(value, ["kind", "rowIds", "bundleId"], ["destination"]) &&
        rowIds(value.rowIds) && typeof value.bundleId === "string" && UUID.test(value.bundleId) &&
        (!Object.hasOwn(value, "destination") || gap(value.destination, true))
        ? value as ExtrasStorageCommand : null;
    case "restore_stash":
      return exactObject(value, ["kind", "bundleId", "destination"]) &&
        typeof value.bundleId === "string" && UUID.test(value.bundleId) && gap(value.destination)
        ? value as ExtrasStorageCommand : null;
    case "restore_stash_rows":
      return exactObject(value, ["kind", "rowIds", "destination"]) &&
        rowIds(value.rowIds) && gap(value.destination)
        ? value as ExtrasStorageCommand : null;
    case "place_stash_rows":
      return exactObject(value, ["kind", "rowIds", "destination"], ["includeDescendants"]) &&
        rowIds(value.rowIds) && gap(value.destination) &&
        (!Object.hasOwn(value, "includeDescendants") || typeof value.includeDescendants === "boolean")
        ? value as ExtrasStorageCommand : null;
    default:
      return null;
  }
}

/** Duplicate is a separate exact operation: never cast it as a row-engine command. */
export function parseExtrasOperationCommand(value: unknown): ExtrasStorageCommand | ExtrasDuplicateCommand | null {
  if (exactObject(value, ["kind", "rowIds", "destination"]) &&
      value.kind === "duplicate_stash_rows" && rowIds(value.rowIds) && gap(value.destination)) {
    return value as ExtrasDuplicateCommand;
  }
  return parseExtrasStorageCommand(value);
}

/** Pure adapter: the service layer will supply authorization and locked server-head CAS. */
export function applyExtrasStorageOperation(
  document: ScriptDocumentV2, rawCommand: unknown, allocateId?: () => string,
): RowEditResultV2 {
  const refused = (code: string, message: string): RowEditResultV2 => ({
    ok: false, document, diagnostics: [{ code, message, jsonPath: "/stash" }],
  });
  let command: ExtrasStorageCommand | ExtrasDuplicateCommand | null;
  try {
    command = parseExtrasOperationCommand(rawCommand);
  } catch {
    return refused("EXTRAS_COMMAND_INVALID", "Provide a plain JSON Extras operation without custom object behavior.");
  }
  if (!command) return refused("EXTRAS_COMMAND_INVALID", "Provide a supported whole-row Extras operation with exact identifiers and locations.");
  if (command.kind === "duplicate_stash_rows") return duplicateExtrasRows(document, command, allocateId);
  try {
    const edited = applyRowEditV2(document, document.rowEditRevision ?? 0, command);
    if (!edited.ok) return edited;
    // Refuse anything that cannot round-trip through the same canonical persistence codec.
    return { ...edited, document: JSON.parse(serializeAuthoringDocumentV2(edited.document)) as ScriptDocumentV2 };
  } catch {
    return refused("EXTRAS_STORAGE_INVALID", "The Extras operation cannot be stored losslessly; review saved references and content.");
  }
}
