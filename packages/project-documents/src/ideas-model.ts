import { Buffer } from "node:buffer";

import { applyRowEditV2 } from "@vera/contracts/authoring-v2";
import type { NoteDraftBlock, RowGapV2, ScriptDocumentV2 } from "@vera/contracts/v2";

import { ProjectDocumentInputError, requireUuid } from "./model.js";

/** Independent authoring sidecar. Never embed populated Ideas in script-document/v2. */
export interface IdeaItemV1 {
  id: string;
  parentId: string | null;
  orderKey: string;
  text: string;
  state: "open" | "incorporated";
  linkedDraftBlockIds: string[];
  collapsed: boolean;
  version: number;
}

export interface IdeaOutlineV1 {
  schemaVersion: "stt-idea-outline/v1";
  documentId: string;
  items: IdeaItemV1[];
}

export const MAX_IDEA_ITEMS = 2_000;
export const MAX_IDEA_DEPTH = 32;
export const MAX_IDEAS_BYTES = 512 * 1024;

const invalid = (): never => { throw new ProjectDocumentInputError("Invalid Ideas outline."); };

function plainObject(value: unknown): value is Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  try {
    if (Object.getPrototypeOf(value) !== Object.prototype) return false;
    return Reflect.ownKeys(value).every((key) =>
      typeof key === "string" && Object.hasOwn(Object.getOwnPropertyDescriptor(value, key) ?? {}, "value"));
  } catch { return false; }
}

function exactKeys(value: Record<string, unknown>, names: readonly string[]): boolean {
  return Reflect.ownKeys(value).length === names.length &&
    names.every((name) => Object.hasOwn(value, name));
}

function orderKey(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= 128 &&
    value.trim().length > 0 && !/\p{Cc}/u.test(value);
}

function positiveVersion(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

/** Existing projects have a synthetic revision-zero outline until their first write. */
export function emptyIdeasV1(documentId: string): IdeaOutlineV1 {
  return { schemaVersion: "stt-idea-outline/v1", documentId: requireUuid(documentId), items: [] };
}

/**
 * Closed, JSON-compatible, bounded preorder representation. Siblings are in
 * strictly increasing code-unit order; every parent's subtree is contiguous.
 * All text is preserved byte-for-byte (including whitespace and newlines).
 */
export function checkedIdeas(input: unknown, expectedDocumentId: string): IdeaOutlineV1 {
  if (!plainObject(input) || !exactKeys(input, ["schemaVersion", "documentId", "items"]) ||
      input.schemaVersion !== "stt-idea-outline/v1" || !Array.isArray(input.items) ||
      input.items.length > MAX_IDEA_ITEMS ||
      requireUuid(input.documentId) !== requireUuid(expectedDocumentId)) return invalid();

  const ids = new Set<string>();
  const linksSeen = new Set<string>();
  const lastSiblingKey = new Map<string, string>();
  const items: IdeaItemV1[] = [];
  let ancestry: string[] = [];

  for (const raw of input.items) {
    if (!plainObject(raw) || !exactKeys(raw, ["id", "parentId", "orderKey", "text", "state",
      "linkedDraftBlockIds", "collapsed", "version"]) ||
        !orderKey(raw.orderKey) || typeof raw.text !== "string" || raw.text.length === 0 ||
        raw.text.length > 32_768 || (raw.state !== "open" && raw.state !== "incorporated") ||
        typeof raw.collapsed !== "boolean" || !positiveVersion(raw.version) ||
        !Array.isArray(raw.linkedDraftBlockIds) || raw.linkedDraftBlockIds.length > MAX_IDEA_ITEMS) {
      return invalid();
    }
    const id = requireUuid(raw.id);
    const parentId = raw.parentId === null ? null : requireUuid(raw.parentId);
    if (ids.has(id)) return invalid();

    if (parentId === null) ancestry = [];
    else {
      const index = ancestry.indexOf(parentId);
      // A parent that has already closed its subtree cannot be reopened.
      if (index === -1) return invalid();
      ancestry = ancestry.slice(0, index + 1);
    }
    if (ancestry.length + 1 > MAX_IDEA_DEPTH) return invalid();
    const parentKey = parentId ?? "root";
    const previous = lastSiblingKey.get(parentKey);
    if (previous !== undefined && previous >= raw.orderKey) return invalid();
    lastSiblingKey.set(parentKey, raw.orderKey);

    const linkedDraftBlockIds: string[] = [];
    for (const link of raw.linkedDraftBlockIds) {
      const normalized = requireUuid(link);
      // Every Draft block has one unambiguous source Idea.
      if (linksSeen.has(normalized)) return invalid();
      linksSeen.add(normalized);
      linkedDraftBlockIds.push(normalized);
    }

    ids.add(id);
    items.push({
      id, parentId, orderKey: raw.orderKey, text: raw.text, state: raw.state,
      linkedDraftBlockIds, collapsed: raw.collapsed, version: raw.version,
    });
    ancestry.push(id);
  }

  const result: IdeaOutlineV1 = {
    schemaVersion: "stt-idea-outline/v1", documentId: requireUuid(input.documentId), items,
  };
  if (Buffer.byteLength(JSON.stringify(result), "utf8") > MAX_IDEAS_BYTES) return invalid();
  return result;
}

/** Validate the closed placement envelope before any authorized DB transaction. */
export function checkedPromotionPositionV1(
  requestedOrderKey: unknown, destination: unknown,
): { orderKey: string; destination: RowGapV2 } {
  if (!orderKey(requestedOrderKey) || !plainObject(destination) ||
      !exactKeys(destination, ["sectionId", "afterRowId", "beforeRowId"])) return invalid();
  return {
    orderKey: requestedOrderKey,
    destination: {
      sectionId: destination.sectionId === null ? null : requireUuid(destination.sectionId),
      afterRowId: destination.afterRowId === null ? null : requireUuid(destination.afterRowId),
      beforeRowId: destination.beforeRowId === null ? null : requireUuid(destination.beforeRowId),
    },
  };
}

/**
 * Does not mutate source objects or grant build eligibility: the only inserted
 * Draft row is a normal, explicitly excluded note_draft. Authorization and
 * atomic cross-head CAS belong to the transactional service in phase 3.
 */
export function promoteIdeaToNoteV1(
  document: ScriptDocumentV2, outline: IdeaOutlineV1,
  ideaId: string, blockId: string, requestedOrderKey: string, destination: RowGapV2,
): { document: ScriptDocumentV2; ideas: IdeaOutlineV1 } {
  const ideas = checkedIdeas(outline, document.id);
  const placement = checkedPromotionPositionV1(requestedOrderKey, destination);
  const sourceId = requireUuid(ideaId);
  const newId = requireUuid(blockId);
  const source = ideas.items.find((item) => item.id === sourceId);
  if (!source || source.version === Number.MAX_SAFE_INTEGER ||
      ideas.items.some((item) => item.id === newId || item.linkedDraftBlockIds.includes(newId))) {
    return invalid();
  }
  const row: NoteDraftBlock = {
    type: "note_draft", id: newId, orderKey: placement.orderKey,
    text: source.text, state: "excluded", version: 1,
  };
  const edited = applyRowEditV2(document, document.rowEditRevision ?? 0,
    { kind: "create_row", row, destination: placement.destination });
  if (!edited.ok) return invalid();
  const promoted = {
    ...ideas,
    items: ideas.items.map((item) => item.id === sourceId ? {
      ...item, state: "incorporated" as const, version: item.version + 1,
      linkedDraftBlockIds: [...item.linkedDraftBlockIds, newId],
    } : item),
  };
  return { document: edited.document, ideas: checkedIdeas(promoted, document.id) };
}
